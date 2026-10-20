"""Lecture assistee d'un rapport annuel PDF.

Un PDF ne contient pas de tableau au sens informatique : seulement du texte place sur la
page. On procede donc par reperes :
  1. les lignes d'en-tete qui portent plusieurs annees (« 2024   2023 ») fixent les colonnes ;
  2. une ligne dont le libelle ressemble a un poste connu (« Chiffre d'affaires »,
     « Résultat net part du Groupe »…) et qui se termine par des nombres donne les valeurs ;
  3. une mention « en millions d'euros » (ou milliers, milliards) fixe l'unite.

Rien n'est enregistre ici : le resultat est une PROPOSITION, que l'utilisateur relit et
corrige avant de valider (extraction de PDF = jamais parfaite).
"""
import io
import re

import pdfplumber
from fastapi import HTTPException

from backend.db.champs import PAR_CLE
from backend.services.import_service import _normaliser, _poste

PAGES_MAX = 600
ANNEE = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")
# Nombre « a la francaise » ou anglaise : 27 607,6 · 1,234.5 · (1 234) · -3,35 · 12.5
NOMBRE = re.compile(
    r"(?<![\w,.])\(?-?\d{1,3}(?:[   ]\d{3})*(?:[.,]\d+)?\)?(?![\w])|(?<![\w,.])\(?-?\d+(?:[.,]\d+)?\)?(?![\w])"
)
UNITES = [
    (re.compile(r"en\s+milliards|in\s+billions|\(md|bn\b", re.IGNORECASE), 1e9),
    (re.compile(r"en\s+millions|in\s+millions|\(m€|m€\)|\(m\$|millions\s+d", re.IGNORECASE), 1e6),
    (re.compile(r"en\s+milliers|in\s+thousands|\(k€|k€\)|milliers\s+d", re.IGNORECASE), 1e3),
]


def _nombre(texte: str) -> float | None:
    negatif = texte.startswith("(") and texte.endswith(")")
    t = texte.strip("()").replace(" ", " ").replace(" ", " ")
    if " " in t:                      # separateur de milliers par espace : virgule decimale
        t = t.replace(" ", "").replace(",", ".")
    elif "," in t and "." in t:       # 1,234.5 (anglais) ou 1.234,5 (allemand)
        t = t.replace(",", "") if t.rfind(".") > t.rfind(",") else t.replace(".", "").replace(",", ".")
    elif "," in t:
        partie = t.split(",")[1]
        t = t.replace(",", "") if len(partie) == 3 and not t.startswith("0") else t.replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if negatif else v


def _unite(texte: str) -> float | None:
    for motif, facteur in UNITES:
        if motif.search(texte):
            return facteur
    return None


def analyser_pdf(contenu: bytes) -> dict:
    try:
        document = pdfplumber.open(io.BytesIO(contenu))
    except Exception as e:
        raise HTTPException(400, f"PDF illisible : {e}") from e

    trouvailles: dict[str, dict] = {}       # poste -> meilleure ligne trouvee
    with document:
        if len(document.pages) > PAGES_MAX:
            raise HTTPException(400, f"PDF trop long ({len(document.pages)} pages, {PAGES_MAX} au plus).")
        for numero, page in enumerate(document.pages, start=1):
            texte = page.extract_text() or ""
            annees: list[int] = []
            unite_page = _unite(texte)
            for ligne in texte.splitlines():
                ligne = ligne.strip()
                entete = [int(a) for a in ANNEE.findall(ligne)]
                if len(entete) >= 2 and len(_normaliser(ANNEE.sub("", ligne))) < 40:
                    annees = entete                    # nouvelle en-tete de colonnes
                    unite_page = _unite(ligne) or unite_page
                    continue
                if not annees:
                    continue
                trouve = _ligne_poste(ligne, annees)
                if trouve is None:
                    continue
                poste, valeurs, libelle = trouve
                # Premiere occurrence = en general l'etat financier principal (avant les notes).
                if poste not in trouvailles or len(valeurs) > len(trouvailles[poste]["valeurs"]):
                    trouvailles[poste] = {"cle": poste, "valeurs": valeurs, "page": numero,
                                          "ligne": libelle, "unite": unite_page}

    if not trouvailles:
        raise HTTPException(400, (
            "Aucun tableau reconnu. Le PDF est peut-être scanné (image sans texte), ou ses libellés "
            "ne correspondent à aucun poste connu. Utilisez plutôt le collage depuis un tableur."))

    unites = [t["unite"] for t in trouvailles.values() if t["unite"] and PAR_CLE[t["cle"]].unite == "monnaie"]
    unite = max(set(unites), key=unites.count) if unites else 1e6
    postes = [
        {"cle": cle, "libelle": PAR_CLE[cle].libelle, "unite": PAR_CLE[cle].unite,
         "valeurs": {str(a): v for a, v in t["valeurs"].items()}, "page": t["page"], "ligne": t["ligne"]}
        for cle, t in trouvailles.items()
    ]
    annees = sorted({int(a) for p in postes for a in p["valeurs"]})
    return {"annees": annees, "postes": postes, "multiplicateur": unite}


def _ligne_poste(ligne: str, annees: list[int]):
    """« Chiffre d'affaires   3   27 058   27 608 » -> (chiffre_affaires, {2024: 27058, 2023: 27608})."""
    nombres = list(NOMBRE.finditer(ligne))
    if len(nombres) < len(annees):
        return None
    libelle = ligne[:nombres[0].start()].strip(" .:-–—")
    poste = _poste(libelle)
    if poste is None:
        return None
    valeurs = [_nombre(m.group()) for m in nombres]
    # Une reference de note (« Note 4 », « 3 ») precede parfois les montants.
    note = valeurs[0] is not None and float(valeurs[0]).is_integer() and abs(valeurs[0]) < 50
    if len(valeurs) > len(annees) and note:
        valeurs = valeurs[1:]
    valeurs = valeurs[:len(annees)]
    if any(v is None for v in valeurs):
        return None
    return poste, dict(zip(annees, valeurs, strict=True)), libelle
