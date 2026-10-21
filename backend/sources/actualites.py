"""Actualites d'une societe : Google Actualites en francais (flux RSS public), Yahoo en secours.

Rien n'est stocke : les titres sont lus a la demande et gardes une heure en memoire.
"""
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import yfinance as yf

from backend.sources.esef import _mots
from backend.sources.reseau import ErreurReseau, obtenir

URL = "https://news.google.com/rss/search"
DUREE_CACHE = 3600
_cache: dict[str, tuple[float, list[dict]]] = {}


def _requete(nom: str) -> str:
    """« L'Air Liquide S.A. » -> « "air liquide" » : le nom sans forme juridique, entre guillemets."""
    mots = _mots(nom)
    return f'"{" ".join(mots[:4])}"' if mots else nom


def actualites(nom: str, symbole: str, nombre: int = 20) -> list[dict]:
    cle = f"{nom}|{symbole}"
    if cle in _cache and time.monotonic() - _cache[cle][0] < DUREE_CACHE:
        return _cache[cle][1]
    articles = _google(nom, nombre) or _yahoo(nom, nombre)
    _cache[cle] = (time.monotonic(), articles)
    return articles


def _google(nom: str, nombre: int) -> list[dict]:
    try:
        reponse = obtenir(URL, params={"q": f"{_requete(nom)} when:60d", "hl": "fr", "gl": "FR", "ceid": "FR:fr"})
        racine = ET.fromstring(reponse.content)
    except (ErreurReseau, ET.ParseError):
        return []
    articles = []
    for item in racine.findall("./channel/item")[:max(nombre * 3, 60)]:
        try:
            moment = parsedate_to_datetime(item.findtext("pubDate") or "").isoformat()
        except (TypeError, ValueError):
            moment = None
        source = item.findtext("source") or ""
        titre = (item.findtext("title") or "").removesuffix(f" - {source}")
        articles.append({"titre": titre, "lien": item.findtext("link"), "source": source, "moment": moment})
    return sorted(articles, key=lambda a: a["moment"] or "", reverse=True)[:nombre]


def _yahoo(nom: str, nombre: int) -> list[dict]:
    try:
        resultats = yf.Search(nom, news_count=nombre, max_results=1).news
    except Exception:
        return []
    return [{"titre": n.get("title"), "lien": n.get("link"), "source": n.get("publisher"),
             "moment": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(n["providerPublishTime"]))
             if n.get("providerPublishTime") else None}
            for n in resultats]
