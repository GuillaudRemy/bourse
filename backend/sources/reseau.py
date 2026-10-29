"""Acces reseau commun a toutes les sources : delais, nouvelles tentatives, debit limite.

Chaque site a son propre rythme maximal (la SEC impose 10 requetes par seconde au plus) ;
les erreurs passageres (429, 5xx, coupure) sont retentees avec une attente croissante.
"""
import threading
import time
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.core import brut

DELAI = (5, 30)                       # connexion, lecture (secondes)
INTERVALLE_MIN = {                    # secondes entre deux requetes vers un meme site
    "data.sec.gov": 0.15,
    "www.sec.gov": 0.15,
    # Quota non publie : erreurs 429 des 4 a 5 requetes rapprochees ; 1 toutes les 3 s tient (mesure le 28/10/2026).
    "filings.xbrl.org": 3.0,
    "api.gleif.org": 0.2,
}
AGENT = "Bourse (+https://github.com/GuillaudRemy/bourse)"   # on dit qui on est


class ErreurReseau(Exception):
    """Le site ne repond pas, ou repond une erreur apres toutes les tentatives."""


_session = requests.Session()
_session.mount("https://", HTTPAdapter(max_retries=Retry(
    total=3, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET",), respect_retry_after_header=True,
)))
_verrou = threading.Lock()
_dernier_appel: dict[str, float] = {}


def _patienter(hote: str) -> None:
    intervalle = INTERVALLE_MIN.get(hote, 0)
    if not intervalle:
        return
    with _verrou:
        attente = _dernier_appel.get(hote, 0) + intervalle - time.monotonic()
        if attente > 0:
            time.sleep(attente)
        _dernier_appel[hote] = time.monotonic()


def obtenir(url: str, *, entetes: dict | None = None, params: dict | None = None,
            delai=DELAI) -> requests.Response:
    hote = urlparse(url).hostname or ""
    _patienter(hote)
    try:
        reponse = _session.get(url, headers={"User-Agent": AGENT, **(entetes or {})},
                               params=params, timeout=delai)
    except requests.RequestException as e:
        raise ErreurReseau(f"{hote} injoignable : {e}") from e
    if reponse.status_code >= 400:
        raise ErreurReseau(f"{hote} : erreur {reponse.status_code}")
    brut.conserver(hote, urlparse(reponse.url).path, reponse.content)
    return reponse


def json_(url: str, **kwargs):
    reponse = obtenir(url, **kwargs)
    try:
        return reponse.json()
    except ValueError as e:
        raise ErreurReseau(f"{urlparse(url).hostname} : reponse illisible") from e


def avec_tentatives(fonction, *args, tentatives: int = 3, attente: float = 2.0, **kwargs):
    """Pour les appels qui ne passent pas par `obtenir` (bibliotheque yfinance)."""
    for essai in range(tentatives):
        try:
            return fonction(*args, **kwargs)
        except Exception:
            if essai == tentatives - 1:
                raise
            time.sleep(attente * (2 ** essai))
