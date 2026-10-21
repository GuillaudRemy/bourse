"""Projection probabiliste, coherente avec la methode de la droite.

Modele : cours = tendance (la droite) x exp(ecart). L'ecart a la droite n'erre pas au hasard :
il revient vers 0 (c'est l'hypothese meme de la methode). On l'estime comme un processus
autoregressif mensuel ajuste sur l'historique de l'action :

    ecart(t+1) = phi x ecart(t) + choc,      choc ~ loi normale ou loi de Student (queues epaisses)

puis on simule des milliers de trajectoires depuis l'ecart actuel. La pente de la droite n'est
pas connue exactement : chaque trajectoire tire la sienne autour de la pente mesuree, avec
l'erreur type d'une croissance moyenne estimee sur N annees (volatilite annuelle / racine de N). On en tire, pour chaque
horizon, la distribution du rendement annuel et la probabilite de gain.

A cote, la probabilite OBSERVEE dans le passe de l'action : partant d'un ecart semblable a
celui d'aujourd'hui, combien de fois le cours est-il revenu a sa droite en 1, 3, 5 ans ?
Le passe ne garantit rien, mais il dit ce que cette action a l'habitude de faire.
"""
from typing import Any

import numpy as np
import pandas as pd

from backend.analyse.regression import Regression

HORIZONS = [1, 3, 5, 10]
TRAJECTOIRES = 4000
DDL_STUDENT = 4          # degres de liberte : queues nettement plus epaisses que la loi normale
GRAINE = 20240101        # resultats reproductibles d'un affichage a l'autre


def _ar1(ecarts: np.ndarray) -> tuple[float, float]:
    """phi et ecart-type des chocs d'un AR(1) sans constante (l'ecart moyen a la droite est nul)."""
    x, y = ecarts[:-1], ecarts[1:]
    phi = float(np.dot(x, y) / np.dot(x, x)) if np.dot(x, x) > 0 else 0.0
    phi = min(max(phi, 0.0), 0.995)                     # pas d'explosion ni d'oscillation absurde
    chocs = y - phi * x
    return phi, float(np.std(chocs, ddof=1))


def simuler(reg: Regression, loi: str = "normale") -> dict:
    mensuel = reg.residus.resample("ME").last().dropna()
    if len(mensuel) < 36:
        return {}
    phi, sigma = _ar1(mensuel.to_numpy())
    rng = np.random.default_rng(GRAINE)
    mois = max(HORIZONS) * 12
    annees_mesure = max((reg.fin - reg.debut).days / 365.25, 1)
    log_prix = (reg.residus + reg.b * reg.annees(reg.residus.index)).resample("ME").last().dropna()
    volatilite = float(np.std(np.diff(log_prix.to_numpy()), ddof=1) * np.sqrt(12))
    erreur_pente = volatilite / np.sqrt(annees_mesure)
    pentes = rng.normal(reg.b, erreur_pente, size=(TRAJECTOIRES, 1)) / 12
    if loi == "student":
        chocs = rng.standard_t(DDL_STUDENT, size=(TRAJECTOIRES, mois)) * np.sqrt((DDL_STUDENT - 2) / DDL_STUDENT)
    else:
        chocs = rng.standard_normal((TRAJECTOIRES, mois))
    chocs *= sigma

    ecart = np.empty((TRAJECTOIRES, mois))
    courant = np.full(TRAJECTOIRES, float(reg.residus.iloc[-1]))
    for m in range(mois):
        courant = phi * courant + chocs[:, m]
        ecart[:, m] = courant
    # Rendement cumule (log) depuis aujourd'hui = tendance + variation de l'ecart.
    log_rendement = pentes * np.arange(1, mois + 1) + ecart - float(reg.residus.iloc[-1])

    horizons = []
    for annees in HORIZONS:
        total = log_rendement[:, annees * 12 - 1]
        annuel = np.exp(total / annees) - 1
        horizons.append({
            "annees": annees,
            "p5": float(np.percentile(annuel, 5)), "p25": float(np.percentile(annuel, 25)),
            "mediane": float(np.median(annuel)),
            "p75": float(np.percentile(annuel, 75)), "p95": float(np.percentile(annuel, 95)),
            "proba_gain": float(np.mean(total > 0)),
        })
    # Cone mensuel (multiplicateur du cours actuel), pour le graphique.
    cone = {f"p{p}": np.exp(np.percentile(log_rendement, p, axis=0)).round(4).tolist() for p in (5, 25, 50, 75, 95)}
    demi_vie = float(np.log(0.5) / np.log(phi)) if 0 < phi < 1 else None
    return {"loi": loi, "phi": phi, "erreur_pente": float(np.exp(erreur_pente) - 1), "demi_vie_mois": demi_vie,
            "horizons": horizons, "cone": cone}


def retour_observe(reg: Regression) -> dict:
    """Dans le passe : depuis un ecart au moins aussi grand qu'aujourd'hui (du meme cote),
    part des cas revenus a la droite dans 1, 3 et 5 ans."""
    z = (reg.residus / reg.sigma).to_numpy() if reg.sigma > 0 else np.zeros(len(reg.residus))
    actuel = z[-1]
    if abs(actuel) < 0.25:
        return {"position": float(actuel), "sur_la_droite": True}
    dessous = actuel < 0
    departs = np.where(z <= actuel)[0] if dessous else np.where(z >= actuel)[0]
    seances = 252
    # Jours consecutifs = un seul episode : c'est le nombre d'episodes qui dit si la statistique est solide.
    episodes = int(1 + np.sum(np.diff(departs) > 20)) if len(departs) else 0
    resultat: dict[str, Any] = {"position": float(actuel), "sur_la_droite": False, "cas": int(len(departs)),
                "episodes": episodes, "horizons": []}
    for annees in (1, 3, 5):
        h = annees * seances
        utiles = [d for d in departs if d + h < len(z)]
        if len(utiles) < 20:
            continue
        revenus = [bool((z[d:d + h] >= 0).any() if dessous else (z[d:d + h] <= 0).any()) for d in utiles]
        resultat["horizons"].append({"annees": annees, "proba": float(np.mean(revenus)), "cas": len(utiles)})
    return resultat


def analyser(reg: Regression, fin: pd.Timestamp) -> dict:
    normale, student = simuler(reg, "normale"), simuler(reg, "student")
    if not normale:
        return {}
    mois = pd.date_range(fin + pd.offsets.MonthEnd(1), periods=max(HORIZONS) * 12, freq="ME")
    return {
        "normale": {k: v for k, v in normale.items() if k != "cone"},
        "student": {k: v for k, v in student.items() if k != "cone"},
        "cone": {"jours": [d.strftime("%Y-%m-%d") for d in mois], **student["cone"]},
        "retour": retour_observe(reg),
    }
