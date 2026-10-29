"""Archives de l'AMF (base BDIF) : documents de reference et documents d'enregistrement universel des
societes cotees a Paris, depuis 2005 environ.

C'est la seule source gratuite des comptes europeens d'avant ESEF (2020) : ESEF ne remonte qu'a 2020, Yahoo
a 4-5 ans. Chaque document contient les chiffres cles de 3 a 5 exercices ; ils passent par la lecture
assistee de PDF de l'application, relue par l'utilisateur avant enregistrement.
"""
from backend.sources.base import SourceIndisponible
from backend.sources.esef import _mots
from backend.sources.reseau import ErreurReseau, json_, obtenir

API = "https://bdif.amf-france.org/back/api/v1"
TYPES = ("DocumentReference", "DocumentEnregistrementUniversel")


def couvre(symbole: str, isin: str | None, pays: str | None) -> bool:
    return symbole.upper().endswith(".PA") or (isin or "").startswith("FR") or pays == "France"


def _meme_societe(nom: str, raison_sociale: str) -> bool:
    mots, candidats = _mots(nom), set(_mots(raison_sociale))
    return bool(mots) and sum(m in candidats for m in mots) / len(mots) >= 0.75


def documents(nom: str) -> list[dict]:
    """Documents annuels de la societe, du plus recent au plus ancien : [{annee, type, date, fichier, chemin}]."""
    mots = _mots(nom)
    if not mots:
        return []
    try:
        reponse = json_(f"{API}/informations", params={
            "typesInformation": "VISA", "typesDocument": list(TYPES), "rechercheTexte": max(mots, key=len),
            "from": 0, "size": 100})
    except ErreurReseau as e:
        raise SourceIndisponible(f"AMF : recherche impossible ({e})") from e
    resultat: dict[int, dict] = {}
    for r in reponse.get("result") or []:
        if not any(_meme_societe(nom, s.get("raisonSociale") or "") for s in r.get("societes") or []):
            continue
        pdfs = [d for d in r.get("documents") or [] if d.get("accessible") and d["nomFichier"].lower().endswith(".pdf")]
        if not pdfs or not r.get("anneeComptable"):
            continue
        # « 2019-020800.pdf » est le document ; « 2019-0208.pdf », la page de visa de l'AMF.
        principal = next((d for d in pdfs if d["nomFichier"].lower().endswith("00.pdf")), pdfs[-1])
        annee = int(r["anneeComptable"])
        resultat.setdefault(annee, {
            "annee": annee, "type": (r.get("typesDocument") or [""])[0], "date": (r.get("dateInformation") or "")[:10],
            "fichier": principal["nomFichier"], "chemin": principal["path"]})
    return sorted(resultat.values(), key=lambda d: -d["annee"])


def telecharger(chemin: str) -> bytes:
    if ".." in chemin or not chemin.lower().endswith(".pdf"):
        raise SourceIndisponible("AMF : chemin de document invalide.")
    try:
        return obtenir(f"{API}/documents/{chemin}", delai=(10, 180)).content
    except ErreurReseau as e:
        raise SourceIndisponible(f"AMF : téléchargement impossible ({e})") from e
