"""Modele de langage LOCAL via Ollama (https://ollama.com) : rien ne sort de l'ordinateur.

L'assistant n'apparait que si Ollama repond sur cette machine et qu'au moins un modele est
installe. Seules les adresses locales sont acceptees : on ne parle jamais a un serveur distant.
Pour l'instant, l'assistant est reserve a Linux (Ubuntu).
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Iterator
from urllib.parse import urlparse

ADRESSE = os.environ.get("BOURSE_OLLAMA", "http://127.0.0.1:11434")
HOTES_LOCAUX = {"127.0.0.1", "localhost", "::1"}
PLATEFORMES = ("linux",)
# Ordre de preference quand aucun modele n'est choisi dans les reglages.
PREFERES = ["qwen3.5", "qwen3", "gemma4:e4b", "gemma4", "mistral-small", "llama3.1", "mistral", "llama3"]
CONTEXTE = 8192                       # jetons : assez pour 3 pages de rapport et la consigne


class OllamaIndisponible(Exception):
    pass


def _url(chemin: str) -> str:
    if urlparse(ADRESSE).hostname not in HOTES_LOCAUX:
        raise OllamaIndisponible("Adresse d'Ollama non locale : refusée (l'assistant ne fonctionne qu'en local).")
    return ADRESSE.rstrip("/") + chemin


def _requete(chemin: str, corps: dict | None = None, delai: float = 5):
    donnees = json.dumps(corps).encode() if corps is not None else None
    requete = urllib.request.Request(_url(chemin), data=donnees, headers={"Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(requete, timeout=delai)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise OllamaIndisponible(f"Ollama a refusé la demande ({e.code}) : {detail[:300]}") from e
    except OSError as e:
        raise OllamaIndisponible(f"Ollama ne répond pas ({e}).") from e


def modeles() -> list[dict]:
    with _requete("/api/tags", delai=2) as r:
        return [{"nom": m["name"], "taille": m.get("size"), "parametres": m.get("details", {}).get("parameter_size")}
                for m in json.load(r).get("models", [])]


def choisir(installes: list[str], reglage: str | None) -> str | None:
    if reglage and reglage in installes:
        return reglage
    for prefixe in PREFERES:
        if (trouve := next((m for m in installes if m.startswith(prefixe)), None)):
            return trouve
    return installes[0] if installes else None


def etat(reglage: str | None = None) -> dict:
    if not sys.platform.startswith(PLATEFORMES):
        return {"disponible": False, "raison": "L'assistant est disponible sous Ubuntu pour l'instant."}
    try:
        liste = modeles()
    except OllamaIndisponible as e:
        return {"disponible": False, "raison": f"Ollama n'est pas lancé sur cet ordinateur ({e})."}
    if not liste:
        return {"disponible": False, "raison": "Ollama est installé mais aucun modèle n'est téléchargé (ollama pull qwen3.5:9b)."}
    return {"disponible": True, "modeles": liste, "modele": choisir([m["nom"] for m in liste], reglage)}


def _corps(modele: str, messages: list[dict], schema: dict | None, flux: bool, temperature: float,
           contexte: int = CONTEXTE) -> dict:
    corps = {"model": modele, "messages": messages, "stream": flux, "think": False,
             "options": {"temperature": temperature, "num_ctx": contexte}}
    if schema:
        corps["format"] = schema
    return corps


def discuter(modele: str, messages: list[dict], schema: dict | None = None, temperature: float = 0.2,
             delai: float = 600, contexte: int = CONTEXTE) -> str:
    """Reponse complete. Avec `schema` (JSON Schema), Ollama contraint la sortie a ce format.
    Attention : au-dela de `contexte` jetons, Ollama coupe le DEBUT de la conversation (consigne comprise)."""
    corps = _corps(modele, messages, schema, False, temperature, contexte)
    try:
        with _requete("/api/chat", corps, delai) as r:
            return json.load(r)["message"]["content"]
    except OllamaIndisponible as e:
        if "think" not in str(e):
            raise
        corps.pop("think")            # modele sans mode « reflexion » : on redemande sans l'option
        with _requete("/api/chat", corps, delai) as r:
            return json.load(r)["message"]["content"]


def flux(modele: str, messages: list[dict], temperature: float = 0.3, delai: float = 600) -> Iterator[str]:
    """Reponse morceau par morceau, pour l'afficher pendant qu'elle s'ecrit."""
    corps = _corps(modele, messages, None, True, temperature)
    try:
        reponse = _requete("/api/chat", corps, delai)
    except OllamaIndisponible as e:
        if "think" not in str(e):
            raise
        corps.pop("think")
        reponse = _requete("/api/chat", corps, delai)
    with reponse:
        for ligne in reponse:
            if ligne.strip():
                morceau = json.loads(ligne)
                if texte := morceau.get("message", {}).get("content"):
                    yield texte
                if morceau.get("done"):
                    return


def json_tolerant(texte: str):
    """Certains modeles ignorent le format demande : bloc ```json, texte autour… on recupere l'objet."""
    texte = re.sub(r"^```(?:json)?\s*|\s*```$", "", texte.strip())
    try:
        return json.loads(texte)
    except ValueError:
        debut, fin = texte.find("{"), texte.rfind("}")
        if debut >= 0 and fin > debut:
            return json.loads(texte[debut:fin + 1])
        raise
