"""Robustesse de la droite de regression.

  · Sensibilite au point de depart : la pente recalculee pour chaque annee de depart
    possible. Si elle bouge beaucoup, la droite depend surtout du moment choisi (creux ou
    sommet) : elle est fragile.
  · Pente glissante : la pente sur 15 ans, recalculee chaque annee. Elle montre si le
    « rythme de croisiere » ralentit ou accelere.
  · Rupture : la date qui coupe le mieux l'historique en deux droites distinctes (test de
    type Chow, sur des points mensuels). Les cours etant fortement autocorreles, la
    statistique F n'est pas une vraie probabilite : on ne retient une rupture que si elle
    est a la fois tres nette ET economiquement importante (pentes tres differentes).
"""
import numpy as np
import pandas as pd

from backend.analyse.regression import ANNEE, ajuster

FENETRE_GLISSANTE = 15
DUREE_MIN_SEGMENT = 36        # mois de part et d'autre d'une rupture candidate
F_NET = 60.0                  # seuil empirique (donnees mensuelles autocorrelees)


def _mensuel(cours: pd.Series) -> pd.Series:
    return cours[cours > 0].resample("ME").last().dropna()


def sensibilite(cours: pd.Series, duree_min: int = 10) -> dict:
    mensuel = _mensuel(cours)
    if mensuel.empty:
        return {"points": []}
    premiere, derniere = mensuel.index[0].year + 1, mensuel.index[-1].year - duree_min
    points = []
    for annee in range(premiere, derniere + 1):
        reg = ajuster(mensuel[mensuel.index >= pd.Timestamp(annee, 1, 1)])
        if reg:
            points.append({"annee": annee, "pente": reg.pente})
    if len(points) < 3:
        return {"points": points}
    pentes = [p["pente"] for p in points]
    ecart = max(pentes) - min(pentes)
    statut = "ok" if ecart < 0.04 else "attention" if ecart < 0.08 else "alerte"
    return {"points": points, "min": min(pentes), "max": max(pentes), "ecart": ecart, "statut": statut}


def pente_glissante(cours: pd.Series, fenetre: int = FENETRE_GLISSANTE) -> list[dict]:
    mensuel = _mensuel(cours)
    if mensuel.empty:
        return []
    resultat = []
    for annee in range(mensuel.index[0].year + fenetre, mensuel.index[-1].year + 1):
        fin = pd.Timestamp(annee, 12, 31)
        reg = ajuster(mensuel[(mensuel.index > fin - pd.DateOffset(years=fenetre)) & (mensuel.index <= fin)])
        if reg:
            resultat.append({"annee": annee, "pente": reg.pente})
    return resultat


def rupture(cours: pd.Series) -> dict | None:
    """Meilleure coupure en deux droites ; None si l'historique est trop court."""
    mensuel = _mensuel(cours)
    n = len(mensuel)
    if n < 2 * DUREE_MIN_SEGMENT + 12:
        return None
    t = (mensuel.index - mensuel.index[0]).days.to_numpy() / ANNEE
    y = np.log(mensuel.to_numpy())

    def sse(tt, yy):
        b, a = np.polyfit(tt, yy, 1)
        return float(np.sum((yy - (a + b * tt)) ** 2)), float(b)

    sse_total, _ = sse(t, y)
    meilleur = None
    for k in range(DUREE_MIN_SEGMENT, n - DUREE_MIN_SEGMENT):
        sse_a, pente_a = sse(t[:k], y[:k])
        sse_b, pente_b = sse(t[k:], y[k:])
        if meilleur is None or sse_a + sse_b < meilleur[0]:
            meilleur = (sse_a + sse_b, k, pente_a, pente_b)
    sse_coupe, k, pente_avant, pente_apres = meilleur
    f = ((sse_total - sse_coupe) / 2) / (sse_coupe / (n - 4)) if sse_coupe > 0 else float("inf")
    avant, apres = float(np.exp(pente_avant) - 1), float(np.exp(pente_apres) - 1)
    ecart = apres - avant
    nette = f > F_NET and abs(ecart) > max(0.06, 0.5 * abs(avant))
    return {
        "date": mensuel.index[k].strftime("%Y-%m-%d"),
        "pente_avant": avant, "pente_apres": apres, "ecart": ecart,
        "f": float(f), "nette": bool(nette),
        "annees_apres": round((mensuel.index[-1] - mensuel.index[k]).days / 365.25, 1),
    }
