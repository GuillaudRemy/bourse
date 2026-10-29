"""Simulateur de patrimoine : versements mensuels, repartition entre classes d'actifs, fourchette de resultats.

Volontairement theorique : chaque classe a un rendement annuel moyen et une volatilite (hypotheses par
defaut tirees de l'histoire longue, ou mesurees sur une valeur suivie), les classes sont correlees, et
3 000 trajectoires mensuelles tirees au hasard donnent une fourchette (10e, 25e, 50e, 75e, 90e centiles).
Le portefeuille est reequilibre chaque annee vers la repartition choisie. Ni frais, ni impots, ni inflation
(sauf si on la retire du rendement : les montants sont alors en euros d'aujourd'hui).
"""
from dataclasses import dataclass

import numpy as np

# rendement annuel moyen, volatilite annuelle (ordres de grandeur sur longue periode, en euros, avant inflation)
CLASSES = {
    "actions":     {"libelle": "Actions (monde)",         "rendement": 0.07,  "volatilite": 0.16},
    "obligations": {"libelle": "Obligations",             "rendement": 0.03,  "volatilite": 0.06},
    "or":          {"libelle": "Or",                      "rendement": 0.05,  "volatilite": 0.15},
    "fonds_euros": {"libelle": "Fonds en euros",          "rendement": 0.025, "volatilite": 0.0},
    "monetaire":   {"libelle": "Livret / monétaire",      "rendement": 0.02,  "volatilite": 0.0},
}
CORRELATIONS = {("actions", "obligations"): 0.1, ("actions", "or"): 0.05, ("obligations", "or"): 0.2}
TRAJECTOIRES = 3000
CENTILES = (10, 25, 50, 75, 90)


@dataclass
class Poche:
    classe: str
    part: float                  # fraction du portefeuille (la somme vaut 1)
    rendement: float
    volatilite: float


def correlation(a: str, b: str) -> float:
    return 1.0 if a == b else CORRELATIONS.get((a, b), CORRELATIONS.get((b, a), 0.0))


def simuler(poches: list[Poche], versement: float, capital: float, annees: int, inflation: float = 0.0,
            graine: int = 7) -> dict:
    if not poches or abs(sum(p.part for p in poches) - 1) > 1e-6:
        raise ValueError("La répartition doit totaliser 100 %.")
    mois = annees * 12
    n = len(poches)
    parts = np.array([p.part for p in poches])
    # Rendements mensuels log-normaux : moyenne geometrique annuelle = `rendement` (moins l'inflation).
    vol_m = np.array([p.volatilite for p in poches]) / np.sqrt(12)
    mu_m = np.log1p(np.array([p.rendement for p in poches]) - inflation) / 12
    cov = np.array([[correlation(a.classe, b.classe) * vol_m[i] * vol_m[j] for j, b in enumerate(poches)]
                    for i, a in enumerate(poches)])
    rng = np.random.default_rng(graine)
    tirages = rng.multivariate_normal(np.zeros(n), cov, size=(TRAJECTOIRES, mois), method="svd") if cov.any() \
        else np.zeros((TRAJECTOIRES, mois, n))
    croissance = np.exp(mu_m + tirages)                       # (trajectoires, mois, poches)

    avoirs = np.tile(capital * parts, (TRAJECTOIRES, 1))
    totaux = np.empty((TRAJECTOIRES, mois + 1))
    totaux[:, 0] = capital
    for m in range(mois):
        avoirs = avoirs * croissance[:, m, :] + versement * parts
        if (m + 1) % 12 == 0:                                 # reequilibrage annuel
            avoirs = avoirs.sum(axis=1, keepdims=True) * parts
        totaux[:, m + 1] = avoirs.sum(axis=1)

    verse = capital + versement * np.arange(mois + 1)
    courbes = {str(c): np.percentile(totaux, c, axis=0).round(0).tolist() for c in CENTILES}
    jalons = []
    for a in sorted({10, 15, 20, 25, 30, annees} & set(range(1, annees + 1))):
        fin = totaux[:, a * 12]
        jalons.append({
            "annees": a, "verse": float(verse[a * 12]),
            **{f"p{c}": float(np.percentile(fin, c)) for c in CENTILES},
            "proba_perte": float((fin < verse[a * 12]).mean()),
        })
    rendement_moyen = float(sum(p.part * p.rendement for p in poches))
    return {"mois": mois, "verse": verse.round(0).tolist(), "centiles": courbes, "jalons": jalons,
            "rendement_moyen": rendement_moyen - inflation, "trajectoires": TRAJECTOIRES}
