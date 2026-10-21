"""Analyse technique a la demande : unite de temps et parametres choisis par l'utilisateur."""
import pandas as pd
from fastapi import HTTPException
from sqlmodel import Session

from backend.analyse import indicateurs as ind
from backend.db.schema import Valeur
from backend.services.stockage import charger_cours

UNITES = {"jour": None, "semaine": "W-FRI", "mois": "ME"}


def _liste(serie: pd.Series, decimales: int = 4) -> list:
    return [None if pd.isna(v) else round(float(v), decimales) for v in serie]


def regrouper(cours: pd.DataFrame, unite: str) -> pd.DataFrame:
    """Bougies hebdomadaires ou mensuelles a partir des seances."""
    regle = UNITES[unite]
    if regle is None:
        return cours
    groupe = cours.resample(regle)
    df = pd.DataFrame({"ouverture": groupe["ouverture"].first(), "haut": groupe["haut"].max(), "bas": groupe["bas"].min(),
                       "cloture": groupe["cloture"].last(), "ajuste": groupe["ajuste"].last(), "volume": groupe["volume"].sum()})
    return df.dropna(subset=["cloture"])


def technique(db: Session, valeur_id: int, unite: str = "jour", mm: list[int] = (20, 50, 200), rsi: int = 14,
              bollinger: int = 20, stochastique: int = 14, atr: int = 14, adx: int = 14) -> dict:
    if unite not in UNITES:
        raise HTTPException(422, "Unité inconnue (jour, semaine ou mois).")
    if not db.get(Valeur, valeur_id):
        raise HTTPException(404, "Valeur introuvable.")
    cours = charger_cours(db, valeur_id)
    if cours.empty:
        raise HTTPException(409, "Aucun cours.")
    df = regrouper(cours, unite)
    c = df["cloture"]
    # Sans plus haut / plus bas (cours importes), on retombe sur la cloture.
    haut = df["haut"].fillna(c) if df["haut"].notna().any() else c
    bas = df["bas"].fillna(c) if df["bas"].notna().any() else c
    macd = ind.macd(c)
    boll = ind.bollinger(c, bollinger)
    sto = ind.stochastique(haut, bas, c, stochastique)
    dx = ind.adx(haut, bas, c, adx)
    ichi = ind.ichimoku(haut, bas, c)
    return {
        "unite": unite,
        "jours": [j.strftime("%Y-%m-%d") for j in df.index],
        "ouverture": _liste(df["ouverture"]), "haut": _liste(df["haut"]), "bas": _liste(df["bas"]),
        "cloture": _liste(c), "volume": _liste(df["volume"], 0),
        "moyennes": {str(n): _liste(ind.moyenne_mobile(c, n)) for n in mm},
        "volume_moyen": _liste(df["volume"].rolling(20, min_periods=20).mean(), 0),
        "rsi": _liste(ind.rsi(c, rsi), 2),
        "macd": _liste(macd["macd"]), "macd_signal": _liste(macd["signal"]), "macd_histogramme": _liste(macd["histogramme"]),
        "bollinger_haut": _liste(boll["haut"]), "bollinger_bas": _liste(boll["bas"]),
        "stochastique_k": _liste(sto["k"], 2), "stochastique_d": _liste(sto["d"], 2),
        "atr": _liste(ind.atr(haut, bas, c, atr)),
        "adx": _liste(dx["adx"], 2), "di_plus": _liste(dx["di_plus"], 2), "di_moins": _liste(dx["di_moins"], 2),
        "ichimoku": {k: _liste(ichi[k]) for k in ichi.columns},
        "obv": _liste(ind.obv(c, df["volume"]), 0),
        "parametres": {"mm": list(mm), "rsi": rsi, "bollinger": bollinger, "stochastique": stochastique, "atr": atr, "adx": adx},
    }
