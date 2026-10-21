"""Composition des grands indices, lue sur Wikipedia (tableaux publics, mis a jour par la communaute).

Les symboles sont convertis au format Yahoo. La liste est gardee un jour en memoire.
Attention : c'est la composition ACTUELLE (biais du survivant pour un backtest).
"""
import io
import time

import pandas as pd

from backend.sources.base import SourceIndisponible
from backend.sources.reseau import ErreurReseau, obtenir

UNIVERS = {
    "cac40": {"nom": "CAC 40", "url": "https://fr.wikipedia.org/wiki/CAC_40",
              "colonnes": ("Mnémo", "Société", "Secteur"), "suffixe": ".PA"},
    "dax": {"nom": "DAX 40", "url": "https://en.wikipedia.org/wiki/DAX",
            "colonnes": ("Ticker", "Company", "Prime Standard Sector"), "suffixe": ""},
    "eurostoxx50": {"nom": "Euro Stoxx 50", "url": "https://en.wikipedia.org/wiki/EURO_STOXX_50",
                    "colonnes": ("Ticker", "Name", "Sector"), "suffixe": ""},
    "sp500": {"nom": "S&P 500", "url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
              "colonnes": ("Symbol", "Security", "GICS Sector"), "suffixe": "", "cik": "CIK"},
}
DUREE_CACHE = 86400
_cache: dict[str, tuple[float, list[dict]]] = {}


def catalogue() -> list[dict]:
    return [{"cle": cle, "nom": u["nom"]} for cle, u in UNIVERS.items()]


def composition(cle: str) -> list[dict]:
    if cle not in UNIVERS:
        raise SourceIndisponible("Univers inconnu.")
    if cle in _cache and time.monotonic() - _cache[cle][0] < DUREE_CACHE:
        return _cache[cle][1]
    u = UNIVERS[cle]
    try:
        tables = pd.read_html(io.StringIO(obtenir(u["url"]).text))
    except (ErreurReseau, ValueError) as e:
        raise SourceIndisponible(f"Composition de {u['nom']} indisponible : {e}") from e
    symbole, nom, secteur = u["colonnes"]
    table = next((t for t in tables if symbole in t.columns and nom in t.columns and len(t) >= 20), None)
    if table is None:
        raise SourceIndisponible(f"Composition de {u['nom']} : tableau introuvable (page modifiée ?).")
    membres = []
    for _, ligne in table.iterrows():
        code = str(ligne[symbole]).strip()
        if not code or code == "nan":
            continue
        code = code.replace(".", "-") if cle == "sp500" else code     # BRK.B -> BRK-B chez Yahoo
        membres.append({
            "symbole": (code + u["suffixe"]).upper(), "nom": str(ligne[nom]).strip(),
            "secteur": str(ligne[secteur]).strip() if secteur in table.columns else None,
            "cik": str(int(ligne[u["cik"]])) if u.get("cik") and pd.notna(ligne.get(u["cik"])) else None,
        })
    _cache[cle] = (time.monotonic(), membres)
    return membres
