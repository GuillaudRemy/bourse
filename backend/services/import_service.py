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
ALIAS_FONDAMENTAUX = {
    "annee":            ["annee", "year", "exercice", "an"],
    "bpa":              ["bpa", "eps", "dilutedeps", "beneficeparaction", "bnpa"],
    "benefice_net":     ["beneficenet", "netincome", "resultatnet", "benefice"],
    "chiffre_affaires": ["chiffreaffaires", "chiffredaffaires", "ca", "revenue", "totalrevenue", "ventes"],
    "dividende":        ["dividende", "dividend", "dpa", "dividendeparaction"],
}


def _normaliser(nom: str) -> str:
    nom = unicodedata.normalize("NFKD", str(nom)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", nom.lower())


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


def importer_fondamentaux(db: Session, valeur: Valeur, contenu: bytes) -> Resultat:
    df = _lire(contenu)
    colonnes = _associer(df, ALIAS_FONDAMENTAUX)
    if "annee" not in colonnes or len(colonnes) < 2:
        raise HTTPException(400, (
            "Il faut une colonne « annee » et au moins une donnée (bpa, benefice_net, "
            f"chiffre_affaires, dividende). Colonnes lues : {', '.join(df.columns)}."
        ))

    annees = {}
    valeurs = {c: _nombres(df[col]) for c, col in colonnes.items() if c != "annee"}
    for i, brut in enumerate(df[colonnes["annee"]]):
        trouve = re.search(r"(19|20|21)\d{2}", str(brut))
        if trouve:
            annees[int(trouve.group())] = {c: s.iloc[i] for c, s in valeurs.items()}
    if not annees:
        raise HTTPException(400, "Aucune année lisible dans le fichier.")

    nombre = enregistrer_fondamentaux(db, valeur.id, annees, "import", ecraser=True)
    db.commit()
    return Resultat(message=f"{nombre} année(s) importée(s) ({min(annees)} → {max(annees)}).",
                    fondamentaux=nombre)
