"""Import de fichiers CSV, quand aucune API ne couvre la valeur (ou pour completer
les fondamentaux, que Yahoo ne fournit que sur 4 a 5 ans).

Le lecteur est tolerant : separateur `,` `;` ou tabulation, virgule decimale,
dates ISO ou francaises, en-tetes en francais ou en anglais (export Boursorama,
Investing, Yahoo, Excel…).
"""
import csv
import io
import re
import unicodedata

import pandas as pd
from fastapi import HTTPException
from sqlmodel import Session

from backend.db.champs import CHAMPS, PAR_CLE
from backend.db.schema import Valeur
from backend.models.valeur import Resultat
from backend.services.stockage import enregistrer_cours, enregistrer_fondamentaux

# Nom de colonne normalise (minuscules, sans accents ni ponctuation) -> champ.
ALIAS_COURS = {
    "jour":      ["date", "jour", "seance", "datetime", "time"],
    "ouverture": ["ouverture", "ouv", "open", "premier"],
    "haut":      ["haut", "plushaut", "high", "max"],
    "bas":       ["bas", "plusbas", "low", "min"],
    "cloture":   ["cloture", "close", "dernier", "fermeture", "price", "prix", "cours", "last", "valeur"],
    "ajuste":    ["adjclose", "clotureajustee", "ajuste", "coursajuste", "rendementtotal",
                  "dividendesreinvestis", "totalreturn"],
    "volume":    ["volume", "vol", "quantite"],
}
# Synonymes courants des postes (en plus de la cle et du libelle de champs.py).
SYNONYMES = {
    "bpa":              ["eps", "dilutedeps", "beneficeparaction", "bnpa", "bpadilue", "earningspershare",
                         "resultatnetparaction", "resultatparaction", "resultatnetdilueparaction",
                         "dilutedearningspershare", "resultatnetpartdugroupeparaction"],
    "dividende":        ["dividend", "dpa", "dividendeparaction", "dividendpershare", "dps",
                         "dividendeverseparaction", "dividendeproposeparaction"],
    "benefice_net":     ["netincome", "resultatnet", "benefice", "resultatnetpartdugroupe", "netprofit"],
    "chiffre_affaires": ["ca", "revenue", "revenues", "totalrevenue", "ventes", "sales", "turnover"],
    "marge_brute":      ["grossprofit", "margebrute"],
    "ebit":             ["resultatoperationnel", "operatingincome", "resultatdexploitation", "ebit"],
    "ebitda":           ["ebitda", "ebe", "excedentbrutdexploitation"],
    "nombre_actions":   ["shares", "sharesoutstanding", "nombredactions", "actions"],
    "capitaux_propres": ["equity", "stockholdersequity", "fondspropres", "capitauxpropres"],
    "dette_financiere": ["totaldebt", "dettefinanciere", "endettementbrut", "dettebrute"],
    "tresorerie":       ["cash", "cashandequivalents", "tresorerie", "disponibilites"],
    "flux_operationnel": ["operatingcashflow", "fluxoperationnel", "cfo"],
    "capex":            ["capex", "capitalexpenditure", "investissements", "investissementscorporels"],
    "total_actif":      ["totalassets", "totalactif", "totalbilan"],
}
ALIAS_FONDAMENTAUX = {"annee": ["annee", "year", "exercice", "an", "fy"]}


def _normaliser(nom: str) -> str:
    nom = unicodedata.normalize("NFKD", str(nom)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", nom.lower())


def _alias_postes() -> dict[str, list[str]]:
    alias = {}
    for champ in CHAMPS:
        noms = {_normaliser(champ.cle), _normaliser(champ.libelle), *SYNONYMES.get(champ.cle, [])}
        alias[champ.cle] = sorted(noms, key=len, reverse=True)
    return alias


ALIAS_FONDAMENTAUX.update(_alias_postes())


def _poste(libelle: str) -> str | None:
    """Libelle de ligne (tableur, PDF) -> poste. Egalite exacte, ou debut de libelle pour les alias
    longs (« Bénéfice net (part du groupe) » -> benefice_net) ; l'alias le plus long l'emporte
    (« Résultat net par action » -> bpa, pas benefice_net)."""
    nom = _normaliser(libelle)
    if not nom:
        return None
    for cle, noms in ALIAS_FONDAMENTAUX.items():
        if cle != "annee" and nom in noms:
            return cle
    meilleur, longueur = None, 0
    for cle, noms in ALIAS_FONDAMENTAUX.items():
        if cle == "annee":
            continue
        for n in noms:
            if len(n) >= 6 and len(n) > longueur and nom.startswith(n):
                meilleur, longueur = cle, len(n)
    return meilleur


def _lire(contenu: bytes) -> pd.DataFrame:
    for encodage in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texte = contenu.decode(encodage)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(400, "Encodage du fichier non reconnu.")

    texte = texte.strip()
    if not texte:
        raise HTTPException(400, "Le fichier est vide.")
    try:
        separateur = csv.Sniffer().sniff(texte.splitlines()[0], delimiters=",;\t|").delimiter
    except csv.Error:
        separateur = ","
    return pd.read_csv(io.StringIO(texte), sep=separateur, dtype=str, skipinitialspace=True)


def _associer(df: pd.DataFrame, alias: dict[str, list[str]]) -> dict[str, str]:
    """Champ -> nom de colonne du fichier."""
    colonnes = {_normaliser(c): c for c in df.columns}
    trouve = {}
    for champ, noms in alias.items():
        for nom in noms:
            if nom in colonnes and colonnes[nom] not in trouve.values():
                trouve[champ] = colonnes[nom]
                break
    return trouve


def _nombres(serie: pd.Series) -> pd.Series:
    """'1 234,56' · '1,234.56' · '12.5%' · '1.2M' -> float."""
    def convertir(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        s = str(v).strip().replace(" ", "").replace(" ", "").replace("%", "")
        if s in ("", "-", "—", "n/a", "N/A", "NA", "null"):
            return None
        multiplicateur = 1.0
        if s[-1:].upper() in ("K", "M", "B", "G"):
            multiplicateur = {"K": 1e3, "M": 1e6, "B": 1e9, "G": 1e9}[s[-1].upper()]
            s = s[:-1]
        if "," in s and "." in s:
            s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", ".")
        try:
            return float(s) * multiplicateur
        except ValueError:
            return None
    return serie.map(convertir).astype(float)


def _dates(serie: pd.Series) -> pd.Series:
    texte = serie.astype(str).str.strip()
    iso = texte.str.match(r"^\d{4}-\d{2}-\d{2}").mean() > 0.8
    dates = pd.to_datetime(texte, errors="coerce", dayfirst=not iso, format="ISO8601" if iso else None)
    return dates.dt.date


def importer_cours(db: Session, valeur: Valeur, contenu: bytes) -> Resultat:
    df = _lire(contenu)
    colonnes = _associer(df, ALIAS_COURS)
    manquantes = [c for c in ("jour", "cloture") if c not in colonnes]
    if manquantes:
        raise HTTPException(400, (
            "Colonnes introuvables : " + ", ".join(manquantes)
            + f". Colonnes lues : {', '.join(df.columns)}. Il faut au moins une date et un cours de clôture."
        ))

    propre = pd.DataFrame({"jour": _dates(df[colonnes["jour"]])})
    for champ, colonne in colonnes.items():
        if champ != "jour":
            propre[champ] = _nombres(df[colonne])
    propre = propre.dropna(subset=["jour", "cloture"]).drop_duplicates("jour", keep="last")
    if propre.empty:
        raise HTTPException(400, "Aucune ligne exploitable (dates ou cours illisibles).")

    nombre = enregistrer_cours(db, valeur.id, propre.sort_values("jour"))
    db.commit()
    sans_ajuste = "ajuste" not in colonnes
    return Resultat(
        message=(
            f"{nombre} séances importées ({propre['jour'].min():%d/%m/%Y} → {propre['jour'].max():%d/%m/%Y})."
            + (" Pas de colonne « dividendes réinvestis » : la droite utilisera la clôture." if sans_ajuste else "")
        ),
        cours=nombre,
    )


def importer_fondamentaux(db: Session, valeur: Valeur, contenu: bytes, source: str = "import") -> Resultat:
    """Deux dispositions acceptees : une ligne par annee (colonne « annee »), ou une ligne par
    poste avec les annees en colonnes — la forme habituelle d'un tableur ou d'un rapport annuel."""
    df = _lire(contenu)
    annees = _par_annee(df) if "annee" in _associer(df, {"annee": ALIAS_FONDAMENTAUX["annee"]}) \
        else _par_poste(df)
    annees = {a: v for a, v in annees.items() if any(x is not None and not pd.isna(x) for x in v.values())}
    if not annees:
        raise HTTPException(400, (
            "Rien de lisible. Il faut soit une colonne « annee » et des colonnes de postes (bpa, "
            "chiffre_affaires…), soit une ligne par poste avec les années en en-tête. "
            f"Colonnes lues : {', '.join(map(str, df.columns))}."
        ))

    nombre = enregistrer_fondamentaux(db, valeur.id, annees, source)
    db.commit()
    postes = sorted({c for v in annees.values() for c, x in v.items() if x is not None and not pd.isna(x)})
    libelles = ", ".join(PAR_CLE[c].libelle for c in postes)
    return Resultat(message=f"{nombre} année(s) importée(s) ({min(annees)} → {max(annees)}) : {libelles}.",
                    fondamentaux=nombre)


def _annee(texte) -> int | None:
    trouve = re.search(r"(19|20|21)\d{2}", str(texte))
    return int(trouve.group()) if trouve else None


def _par_annee(df: pd.DataFrame) -> dict[int, dict]:
    colonnes = _associer(df, ALIAS_FONDAMENTAUX)
    valeurs = {c: _nombres(df[col]) for c, col in colonnes.items() if c != "annee"}
    annees = {}
    for i, brut in enumerate(df[colonnes["annee"]]):
        if (annee := _annee(brut)) is not None:
            annees[annee] = {c: s.iloc[i] for c, s in valeurs.items()}
    return annees


def _par_poste(df: pd.DataFrame) -> dict[int, dict]:
    colonnes_annees = {col: a for col in df.columns[1:] if (a := _annee(col)) is not None}
    if not colonnes_annees:
        return {}
    annees: dict[int, dict] = {}
    for _, ligne in df.iterrows():
        poste = _poste(ligne.iloc[0])
        if poste is None:
            continue
        valeurs = _nombres(pd.Series([ligne[c] for c in colonnes_annees]))
        for annee, v in zip(colonnes_annees.values(), valeurs, strict=True):
            if v is not None and not pd.isna(v):
                annees.setdefault(annee, {}).setdefault(poste, v)
    return annees
