"""Taux de change de reference de la BCE (gratuits, officiels, quotidiens depuis 1999).

Taux exprimes en unites de devise pour 1 euro (USD 1,08 = 1 euro vaut 1,08 dollar).
"""
import io
from datetime import date

import pandas as pd

from backend.sources.base import SourceIndisponible
from backend.sources.reseau import ErreurReseau, obtenir

NOM = "bce"
URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.{devise}.EUR.SP00.A"
# Sous-unites cotees par Yahoo : pence britanniques, cents sud-africains…
SOUS_UNITES = {"GBp": ("GBP", 100), "GBX": ("GBP", 100), "ZAc": ("ZAR", 100), "ILA": ("ILS", 100)}


def normaliser(devise: str | None) -> tuple[str | None, float]:
    """« GBp » -> (« GBP », 100) : les cours en pence se divisent par 100 avant conversion."""
    if not devise:
        return None, 1
    if devise in SOUS_UNITES:
        return SOUS_UNITES[devise]
    return devise.upper(), 1


def taux(devise: str, debut: date | None = None) -> pd.Series:
    """Serie quotidienne indexee par date ; vide pour l'euro."""
    if devise == "EUR":
        return pd.Series(dtype=float)
    params = {"format": "csvdata"}
    if debut:
        params["startPeriod"] = debut.isoformat()
    try:
        reponse = obtenir(URL.format(devise=devise), params=params, delai=(5, 60))
    except ErreurReseau as e:
        raise SourceIndisponible(f"BCE : taux {devise}/EUR indisponibles ({e})") from e
    df = pd.read_csv(io.StringIO(reponse.text), usecols=["TIME_PERIOD", "OBS_VALUE"])
    serie = pd.Series(df["OBS_VALUE"].to_numpy(dtype=float), index=pd.to_datetime(df["TIME_PERIOD"]))
    return serie.dropna().sort_index()
