"""Le cours face aux benefices : cours = BPA x PER.

  · « Valeur au PER median » : BPA de chaque annee x PER median historique. Si le cours la
    suit, la hausse vient des benefices ; s'il s'en ecarte durablement, elle vient d'une
    renotation (PER qui monte) ou d'une defiance (PER qui baisse).
  · Bande de PER : BPA x PER minimum et maximum observes — l'enveloppe habituelle.
  · Droite du BPA : la meme methode que pour le cours, appliquee aux benefices (regression
    du logarithme du BPA). Sa pente se compare a celle du cours.
"""
import math

import numpy as np
import pandas as pd

ANNEES_MAX = 20     # PER de reference : les 20 dernieres annees au plus
PROJECTION = 3


def analyser(cloture: pd.Series, comptes: list[dict]) -> dict | None:
    """`cloture` : cours non ajuste (le BPA ne contient pas les dividendes), devise des comptes."""
    if cloture.empty:
        return None
    moyennes = cloture.groupby(cloture.index.year).mean()
    lignes = [
        {"annee": c["annee"], "bpa": c["bpa"], "cours_moyen": float(moyennes[c["annee"]]),
         "per": float(moyennes[c["annee"]] / c["bpa"])}
        for c in comptes
        if c.get("bpa") and c["bpa"] > 0 and c["annee"] in moyennes.index
    ]
    if len(lignes) < 3:
        return None
    reference = lignes[-ANNEES_MAX:]
    pers = [l["per"] for l in reference]
    per_min, per_median, per_max = float(np.min(pers)), float(np.median(pers)), float(np.max(pers))

    mensuel = cloture[cloture.index >= pd.Timestamp(lignes[0]["annee"], 1, 1)].resample("ME").last().dropna()
    resultat = {
        # Cours mensuel dans la devise des comptes : comparable au BPA quel que soit l'affichage.
        "cours": {"jours": [d.strftime("%Y-%m-%d") for d in mensuel.index],
                  "valeurs": [round(float(v), 4) for v in mensuel]},
        "annees": [l["annee"] for l in lignes],
        "bpa": [l["bpa"] for l in lignes],
        "per": [l["per"] for l in lignes],
        "cours_moyen": [l["cours_moyen"] for l in lignes],
        "per_min": per_min, "per_median": per_median, "per_max": per_max,
        "valeur_per_median": [l["bpa"] * per_median for l in lignes],
        "valeur_per_min": [l["bpa"] * per_min for l in lignes],
        "valeur_per_max": [l["bpa"] * per_max for l in lignes],
        "per_actuel": float(cloture.iloc[-1] / lignes[-1]["bpa"]),
        "ecart_per_median": float(cloture.iloc[-1] / (lignes[-1]["bpa"] * per_median) - 1),
    }

    if len(lignes) >= 4:
        annees = np.array([l["annee"] for l in lignes], dtype=float)
        y = np.log([l["bpa"] for l in lignes])
        pente, origine = np.polyfit(annees, y, 1)
        ajuste = origine + pente * annees
        variance = float(np.var(y))
        futur = np.arange(annees[-1] + 1, annees[-1] + 1 + PROJECTION)
        resultat["droite_bpa"] = {
            "pente": float(math.exp(pente) - 1),
            "r2": 1 - float(np.var(y - ajuste)) / variance if variance > 0 else 0.0,
            "annees": [int(a) for a in [*annees, *futur]],
            "bpa": [float(math.exp(origine + pente * a)) for a in [*annees, *futur]],
        }
    return resultat
