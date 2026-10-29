"""Comptes des societes cotees en Europe : rapports ESEF (format XBRL obligatoire depuis 2020-2021).

Source : filings.xbrl.org (gratuit, sans cle). Chaque rapport annuel contient l'annee
et l'annee precedente ; en les enchainant du plus ancien au plus recent, on obtient
2019/2020 -> aujourd'hui, les chiffres retraites du rapport le plus recent l'emportant.

Un rapport pese ~15 Mo : les chiffres extraits sont gardes en cache sur disque, on ne
telecharge donc chaque rapport qu'une seule fois.

La societe est retrouvee par son LEI (identifiant d'entite juridique) : saisi a la main,
ou trouve en comparant le nom de la societe a la liste des emetteurs ESEF.
"""
import json
import re
import unicodedata
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from pathlib import Path

from backend.core.config import config
from backend.sources.base import Comptes, Identite, SourceIndisponible
from backend.sources.reseau import ErreurReseau, json_
from backend.sources.xbrl import DELAI_PUBLICATION, IFRS, SOMMES, ajuster_divisions, facteur_divisions, signe

NOM = "esef"
BASE = "https://filings.xbrl.org"
SUFFIXES_EUROPE = {"PA", "AS", "BR", "LS", "MI", "MC", "DE", "F", "VI", "HE", "ST", "CO", "OL", "IR", "AT", "WA",
                   "PR", "BD", "LU", "SW", "IC", "TL", "RG", "VS"}
PAYS_EUROPE = {"France", "Netherlands", "Belgium", "Portugal", "Italy", "Spain", "Germany", "Austria", "Finland",
               "Sweden", "Denmark", "Norway", "Ireland", "Greece", "Poland", "Czech Republic", "Hungary",
               "Luxembourg", "Iceland", "Estonia", "Latvia", "Lithuania", "Slovenia", "Slovakia", "Croatia",
               "Romania", "Bulgaria", "Cyprus", "Malta"}
FORMES_JURIDIQUES = {"sa", "se", "s", "a", "e", "ag", "nv", "plc", "spa", "sca", "sas", "societe", "anonyme",
                     "europeenne", "the", "group", "groupe", "holding", "inc", "ltd", "asa", "ab", "oyj", "as",
                     "en", "commandite", "par", "actions", "de", "la", "le", "l", "et", "and"}
# Postes souvent publies sous un concept « maison » (extension propre a la societe) :
# reconnus par motif quand aucun concept IFRS standard n'est present.
EXTENSIONS = {
    "capex": re.compile(r"^(Acquisition|Purchase|Payments?For|Paiements?|Achats?|Investissements?)D?.*"
                        r"(Immobilisations|PropertyPlant|TangibleAndIntangible|FixedAssets)", re.IGNORECASE),
}
VERSION_CACHE = 2       # a incrementer quand l'extraction change : les rapports seront relus

INSTANTANES = {"total_actif", "actifs_courants", "tresorerie", "creances_clients", "immobilisations_corporelles",
               "goodwill", "passifs_courants", "total_passif", "dette_financiere", "dette_long_terme",
               "capitaux_propres", "resultats_non_distribues"}


def _cache() -> Path:
    dossier = Path(config.DB_NAME).resolve().parent / "cache" / "esef"
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def couvre(identite: Identite) -> bool:
    if identite.type != "action":
        return False
    if identite.lei:
        return True
    suffixe = identite.symbole.rsplit(".", 1)[-1].upper() if "." in identite.symbole else ""
    return suffixe in SUFFIXES_EUROPE or (identite.pays in PAYS_EUROPE)


# ── Recherche du LEI ─────────────────────────────────────────────────
def _mots(nom: str) -> list[str]:
    nom = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
    return [m for m in re.split(r"[^a-z0-9]+", nom) if len(m) > 1 and m not in FORMES_JURIDIQUES]


def trouver_lei(nom: str) -> str | None:
    """Compare le nom (Yahoo) a la liste des emetteurs ESEF ; renvoie le LEI si la correspondance est sure."""
    mots = _mots(nom)
    if not mots:
        return None
    cle = max(mots, key=len)
    try:
        reponse = json_(f"{BASE}/api/entities", params={
            "filter": json.dumps([{"name": "name", "op": "ilike", "val": f"%{cle}%"}]), "page[size]": 50,
        })
    except ErreurReseau as e:
        raise SourceIndisponible(f"ESEF : {e}") from e

    meilleur, score_meilleur = None, 0.0
    for entite in reponse.get("data", []):
        candidats = set(_mots(entite["attributes"]["name"]))
        score = sum(m in candidats for m in mots) / len(mots)
        if score > score_meilleur:
            meilleur, score_meilleur = entite["attributes"]["identifier"], score
    return meilleur if score_meilleur >= 0.75 else None


def lei_par_isin(isin: str) -> str | None:
    """LEI exact d'un emetteur a partir de l'ISIN de son action (GLEIF, base officielle des LEI) :
    plus sur que la comparaison des noms, qui peut confondre deux societes proches."""
    try:
        reponse = json_("https://api.gleif.org/api/v1/lei-records", params={"filter[isin]": isin})
    except ErreurReseau:
        return None
    donnees = reponse.get("data") or []
    return donnees[0]["id"] if len(donnees) == 1 else None


# ── Comptes ──────────────────────────────────────────────────────────
def comptes(identite: Identite, divisions: Sequence[tuple[date, float]] = ()) -> Comptes:
    lei = identite.lei or (identite.isin and lei_par_isin(identite.isin)) or trouver_lei(identite.nom)
    if not lei:
        raise SourceIndisponible(
            f"ESEF : société introuvable pour « {identite.nom} ». Renseignez son LEI dans les réglages de la valeur.")
    identite.decouverts["lei"] = lei

    try:
        depots = json_(f"{BASE}/api/filings", params={
            "filter[entity.identifier]": lei, "page[size]": 100, "sort": "period_end",
        }).get("data", [])
    except ErreurReseau as e:
        raise SourceIndisponible(f"ESEF : {e}") from e
    if not depots:
        raise SourceIndisponible(f"ESEF : aucun rapport publié pour le LEI {lei}.")

    # Un rapport par exercice (le dernier depose si plusieurs langues/versions), du plus ancien au plus recent.
    par_exercice: dict[str, dict] = {}
    for d in depots:
        a = d["attributes"]
        if a.get("json_url") and a.get("period_end"):
            par_exercice[a["period_end"]] = d
    annees: Comptes = {}
    for fin in sorted(par_exercice):
        depot = par_exercice[fin]
        extraits = _extraire(depot)
        reference = date.fromisoformat(fin) + DELAI_PUBLICATION
        facteur = facteur_divisions(list(divisions), reference)
        for annee, valeurs in extraits["annees"].items():
            # Rapport plus recent = chiffres retraites : il remplace l'annee deja connue.
            annees.setdefault(int(annee), {}).update(ajuster_divisions(corriger_echelle(valeurs), facteur))
        if extraits.get("devise"):
            identite.decouverts["devise_comptes"] = extraits["devise"]
    return annees


def corriger_echelle(valeurs: dict) -> dict:
    """Certains depots declarent le BPA et le nombre d'actions avec une echelle fausse (x 1 000 000 : Capgemini,
    exercice 2022). Repere : ramenes a la bonne echelle, ils redeviennent coherents avec bpa = benefice / actions."""
    v = dict(valeurs)
    n, bpa, benefice = v.get("nombre_actions"), v.get("bpa"), v.get("benefice_net")
    if not (n and bpa and benefice):
        return v
    for k in (1e6, 1e3):
        if n > 2e11 and 1e5 < n / k < 5e10 and abs(benefice / (n / k) / (bpa / k) - 1) < 0.15:
            v["nombre_actions"], v["bpa"] = n / k, bpa / k
            if v.get("dividende") and v["dividende"] > 1e3:
                v["dividende"] /= k
            return v
        if abs(bpa) > 1e4 and abs(benefice / n / (bpa / k) - 1) < 0.15:       # le BPA seul est faux
            v["bpa"] = bpa / k
            return v
    return v


def _extraire(depot: dict) -> dict:
    """Chiffres utiles d'un rapport, depuis le cache ou en telechargeant le rapport."""
    fichier = _cache() / f"{depot['id']}-v{VERSION_CACHE}.json"
    if fichier.exists():
        return json.loads(fichier.read_text())
    try:
        rapport = json_(BASE + depot["attributes"]["json_url"], delai=(10, 180))
    except ErreurReseau as e:
        raise SourceIndisponible(f"ESEF : rapport illisible ({e})") from e

    faits: dict[tuple[str, str], float] = {}     # (concept IFRS, periode) -> valeur
    extensions: dict[tuple[str, str], float] = {}  # (concept propre a la societe, periode) -> valeur
    devises: dict[str, int] = {}
    for fait in rapport.get("facts", {}).values():
        dims = fait.get("dimensions", {})
        if set(dims) - {"concept", "entity", "period", "unit"}:     # ventilation (segment, zone…) : ignore
            continue
        concept = dims.get("concept", "")
        try:
            valeur = float(fait["value"])
        except (TypeError, ValueError, KeyError):
            continue
        if not concept.startswith("ifrs-full:"):
            extensions[concept.split(":", 1)[-1], dims.get("period", "")] = valeur
            continue
        unite = dims.get("unit", "")
        if unite.startswith("iso4217:") and "/" not in unite:
            devises[unite[8:]] = devises.get(unite[8:], 0) + 1
        faits[concept[10:], dims.get("period", "")] = valeur

    annees: dict[int, dict[str, float]] = {}
    for cle, candidats in IFRS.items():
        for concept in candidats:
            for (c, periode), valeur in faits.items():
                if c != concept:
                    continue
                annee = _annee(periode, instantane=cle in INSTANTANES)
                if annee is not None and cle not in annees.get(annee, {}):
                    annees.setdefault(annee, {})[cle] = signe(cle, valeur)
    for cle, motif in EXTENSIONS.items():
        for (c, periode), valeur in extensions.items():
            annee = _annee(periode, instantane=cle in INSTANTANES)
            if annee is not None and motif.search(c) and cle not in annees.get(annee, {}):
                annees.setdefault(annee, {})[cle] = signe(cle, valeur)
    for cle, parties in SOMMES.items():
        for annee, valeurs in annees.items():
            if cle in valeurs:
                continue
            morceaux = [v for (c, p), v in faits.items() if c in parties and _annee(p, True) == annee]
            if len(morceaux) == len(parties):
                valeurs[cle] = sum(morceaux)

    extraits = {"annees": annees, "devise": max(devises, key=lambda d: devises[d]) if devises else None}
    fichier.write_text(json.dumps(extraits))
    return extraits


def _annee(periode: str, instantane: bool) -> int | None:
    """xBRL-JSON : « debut/fin » pour une duree, « instant » sinon ; les fins sont exclusives
    (« 2025-01-01T00:00:00 » = cloture au 31/12/2024)."""
    if instantane:
        if "/" in periode:
            return None
        fin = periode
    else:
        if "/" not in periode:
            return None
        debut, fin = periode.split("/")
        duree = (datetime.fromisoformat(fin) - datetime.fromisoformat(debut)).days
        if not 330 <= duree <= 400:
            return None
    return (datetime.fromisoformat(fin) - timedelta(days=1)).year
