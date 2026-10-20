"""Secours pour les cours : l'API « chart » de Yahoo, appelee directement.

La bibliotheque yfinance casse de temps en temps quand Yahoo change ses pages ; cette
API publique, plus simple, survit en general. Elle fournit cours, cours ajuste
(dividendes reinvestis) et divisions, sans cle.
"""
from datetime import UTC, date, datetime

import pandas as pd
from curl_cffi import requests as navigateur

from backend.sources.base import SourceIndisponible
from backend.sources.reseau import avec_tentatives

NOM = "yahoo_direct"
URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbole}"


def _graphique(symbole: str, debut: date | None) -> dict:
    debut_ts = int(datetime(*(debut or date(1970, 1, 2)).timetuple()[:3], tzinfo=UTC).timestamp())
    params = {
        "period1": debut_ts, "period2": int(datetime.now(UTC).timestamp()) + 86400,
        "interval": "1d", "events": "div,split", "includeAdjustedClose": "true",
    }

    def appel():
        # Yahoo refuse les clients qui ne ressemblent pas a un navigateur : curl_cffi imite Chrome.
        reponse = navigateur.get(URL.format(symbole=symbole), params=params, impersonate="chrome", timeout=30)
        if reponse.status_code == 404:
            return reponse.json()
        reponse.raise_for_status()
        return reponse.json()

    try:
        donnees = avec_tentatives(appel)
    except Exception as e:
        raise SourceIndisponible(f"Yahoo (secours) indisponible : {e}") from e
    resultat = (donnees.get("chart") or {}).get("result")
    if not resultat:
        erreur = (donnees.get("chart") or {}).get("error") or {}
        raise SourceIndisponible(f"Yahoo (secours) ne connait pas {symbole} : {erreur.get('description', '')}")
    return resultat[0]


def cours(symbole: str, debut: date | None = None) -> pd.DataFrame:
    g = _graphique(symbole, debut)
    if not g.get("timestamp"):
        return pd.DataFrame()
    decalage = g.get("meta", {}).get("gmtoffset", 0)     # date locale de la place de cotation
    q = g["indicators"]["quote"][0]
    ajuste = (g["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    df = pd.DataFrame({
        "jour": [datetime.fromtimestamp(t + decalage, UTC).date() for t in g["timestamp"]],
        "ouverture": q.get("open"), "haut": q.get("high"), "bas": q.get("low"),
        "cloture": q.get("close"), "ajuste": ajuste, "volume": q.get("volume"),
    })
    return df.dropna(subset=["cloture"]).drop_duplicates("jour", keep="last").reset_index(drop=True)


def divisions(symbole: str) -> list[tuple[date, float]]:
    evenements = (_graphique(symbole, None).get("events") or {}).get("splits") or {}
    resultat = []
    for e in evenements.values():
        if e.get("denominator"):
            ratio = e["numerator"] / e["denominator"]
            if ratio > 0 and ratio != 1:
                resultat.append((datetime.fromtimestamp(e["date"], UTC).date(), ratio))
    return sorted(resultat)
