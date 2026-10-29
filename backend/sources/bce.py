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
# Sous-unites : pence (Londres), cents (Johannesburg, Tel-Aviv) et cents de dollar (« USX », cereales a Chicago).
SOUS_UNITES = {"GBp": ("GBP", 100), "GBX": ("GBP", 100), "ZAc": ("ZAR", 100), "ILA": ("ILS", 100), "USX": ("USD", 100)}


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


SERIES = "https://data-api.ecb.europa.eu/service/data/{cle}"


def serie(cle: str, debut: date | None = None) -> pd.DataFrame:
    """Une serie de taux (courbe des taux, taux directeur, emprunts d'Etat) au format des cours :
    une seance par observation, cloture = ouverture = haut = bas = le taux en %.
    Les series mensuelles (« 2026-09 ») sont datees du dernier jour du mois qu'elles resument."""
    params = {"format": "csvdata"}
    if debut:
        params["startPeriod"] = debut.isoformat()[:7] if "/M." in cle else debut.isoformat()
    try:
        reponse = obtenir(SERIES.format(cle=cle), params=params, delai=(5, 60))
    except ErreurReseau as e:
        raise SourceIndisponible(f"BCE : série {cle} indisponible ({e})") from e
    if not reponse.text.strip():
        return pd.DataFrame()
    df = pd.read_csv(io.StringIO(reponse.text), usecols=["TIME_PERIOD", "OBS_VALUE"]).dropna()
    periodes = df["TIME_PERIOD"].astype(str)
    jours = [pd.Period(p, freq="M").end_time.date() if len(p) == 7 else date.fromisoformat(p) for p in periodes]
    valeurs = df["OBS_VALUE"].astype(float).to_numpy()
    return pd.DataFrame({"jour": jours, "ouverture": valeurs, "haut": valeurs, "bas": valeurs, "cloture": valeurs,
                         "ajuste": valeurs, "volume": None}).drop_duplicates("jour", keep="last").reset_index(drop=True)
