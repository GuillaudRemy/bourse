"""Backtest de la methode : acheter bas dans le couloir, alleger en haut.

SANS BIAIS D'ANTICIPATION : chaque mois, la droite est recalculee uniquement avec les cours
connus a cette date (fenetre croissante, ou glissante de N annees). La droite affichee dans
la fiche, elle, « connait le futur » : un backtest fait avec elle serait faux.

Regle (une valeur) :
  · position ≤ seuil d'achat (ex. -1 σ)  -> investi (si on ne l'etait pas) ;
  · position ≥ seuil de vente (ex. +1 σ) -> vendu, l'argent attend sans rapporter
    (ou au taux `taux_liquidites`) ;
  · entre les deux : on ne bouge pas.
Frais a chaque achat et vente. Comparaison avec « acheter et conserver » sur la meme periode.
"""
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.analyse.regression import ajuster


@dataclass
class Regle:
    seuil_achat: float = -1.0
    seuil_vente: float = 1.0
    frais: float = 0.005              # a l'achat, en fraction du montant (courtage + TTF eventuelle)
    annees_min: int = 10              # historique minimal avant la premiere decision
    fenetre: int | None = None        # None = fenetre croissante ; sinon N dernieres annees
    taux_liquidites: float = 0.0      # rendement annuel de l'argent non investi
    depart_investi: bool = False      # True : investi des le depart (on n'attend pas un premier signal)
    frais_vente: float | None = None  # None : comme a l'achat


def _statistiques(courbe: pd.Series) -> dict:
    if len(courbe) < 2:
        return {}
    annees = (courbe.index[-1] - courbe.index[0]).days / 365.25
    rendements = courbe.pct_change().dropna()
    return {
        "rendement_total": float(courbe.iloc[-1] / courbe.iloc[0] - 1),
        "rendement_annuel": float((courbe.iloc[-1] / courbe.iloc[0]) ** (1 / annees) - 1) if annees > 0 else None,
        "volatilite": float(rendements.std() * math.sqrt(12)),
        "perte_max": float((courbe / courbe.cummax() - 1).min()),
    }


def simuler(cours: pd.Series, regle: Regle) -> dict | None:
    """`cours` : cours quotidiens dividendes reinvestis. Decisions en fin de mois."""
    mensuel = cours[cours > 0].dropna().resample("ME").last().dropna()
    debut_index = next((i for i, j in enumerate(mensuel.index)
                        if (j - mensuel.index[0]).days / 365.25 >= regle.annees_min), None)
    if debut_index is None or debut_index >= len(mensuel) - 12:
        return None

    investi, capital, parts = False, 1.0, 0.0
    if regle.depart_investi:
        investi, capital, parts = True, 0.0, (1 - regle.frais) / float(mensuel.iloc[debut_index])
    courbe, positions, operations, temps_investi = [], [], [], 0
    taux_mensuel = (1 + regle.taux_liquidites) ** (1 / 12) - 1
    for i in range(debut_index, len(mensuel)):
        jour, prix = mensuel.index[i], float(mensuel.iloc[i])
        historique = cours[cours.index <= jour]
        if regle.fenetre:
            historique = historique[historique.index > jour - pd.DateOffset(years=regle.fenetre)]
        reg = ajuster(historique)
        position = reg.position if reg else 0.0
        if not investi:
            capital *= 1 + taux_mensuel
        if not investi and position <= regle.seuil_achat:
            parts = capital * (1 - regle.frais) / prix
            capital, investi = 0.0, True
            operations.append({"jour": jour.strftime("%Y-%m-%d"), "type": "achat", "prix": prix, "position": position})
        elif investi and position >= regle.seuil_vente:
            capital = parts * prix * (1 - (regle.frais if regle.frais_vente is None else regle.frais_vente))
            parts, investi = 0.0, False
            operations.append({"jour": jour.strftime("%Y-%m-%d"), "type": "vente", "prix": prix, "position": position})
        temps_investi += investi
        courbe.append(capital + parts * prix)
        positions.append(position)

    jours = mensuel.index[debut_index:]
    strategie = pd.Series(courbe, index=jours)
    conserver = mensuel.iloc[debut_index:] / mensuel.iloc[debut_index] * (1 - regle.frais)
    return {
        "debut": jours[0].strftime("%Y-%m-%d"), "fin": jours[-1].strftime("%Y-%m-%d"),
        "strategie": _statistiques(strategie), "conserver": _statistiques(conserver),
        "temps_investi": temps_investi / len(jours), "operations": operations,
        "courbe": {"jours": [j.strftime("%Y-%m-%d") for j in jours],
                   "strategie": [round(float(v), 5) for v in strategie],
                   "conserver": [round(float(v), 5) for v in conserver],
                   "position": [round(float(p), 3) for p in positions]},
    }


def agreger(resultats: dict[str, dict]) -> dict:
    """Resume sur un univers : la regle bat-elle « acheter et conserver » ? Moyenne equiponderee."""
    valides = {k: r for k, r in resultats.items() if r and r["strategie"].get("rendement_annuel") is not None}
    if not valides:
        return {}
    ecarts = [r["strategie"]["rendement_annuel"] - r["conserver"]["rendement_annuel"] for r in valides.values()]
    return {
        "valeurs": len(valides),
        "rendement_strategie": float(np.mean([r["strategie"]["rendement_annuel"] for r in valides.values()])),
        "rendement_conserver": float(np.mean([r["conserver"]["rendement_annuel"] for r in valides.values()])),
        "perte_max_strategie": float(np.mean([r["strategie"]["perte_max"] for r in valides.values()])),
        "perte_max_conserver": float(np.mean([r["conserver"]["perte_max"] for r in valides.values()])),
        "part_gagnante": float(np.mean([e > 0 for e in ecarts])),
        "ecart_median": float(np.median(ecarts)),
        "temps_investi": float(np.mean([r["temps_investi"] for r in valides.values()])),
    }
