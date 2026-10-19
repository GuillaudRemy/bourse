"""Droite de regression en echelle logarithmique.

Sur le long terme, le cours d'une action suit approximativement une loi
log-normale (Bachelier, Samuelson, Black-Scholes) : en logarithme, il oscille
autour d'une droite et les ecarts a cette droite se repartissent en cloche.

  · la pente de la droite est le rythme de croisiere annuel ;
  · l'ecart-type des residus donne la largeur du couloir ;
  · la position du dernier cours, en nombre d'ecarts-types, dit si l'action
    est bon marche ou chere par rapport a sa propre tendance.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd

ZONES = [
    # (borne basse en ecarts-types, cle, libelle)
    (-np.inf, "opportunite_manifeste", "Opportunité manifeste"),
    (-2.0,    "sous_evalue",           "Sous-évalué"),
    (-1.0,    "normal",                "Zone normale"),
    (1.0,     "surevalue",             "Surévalué"),
    (2.0,     "surevaluation_manifeste", "Surévaluation manifeste"),
]

# Part du temps attendue par une loi normale dans chaque zone.
THEORIE = {
    "opportunite_manifeste": 0.0228, "sous_evalue": 0.1359, "normal": 0.6827,
    "surevalue": 0.1359, "surevaluation_manifeste": 0.0228,
}

ANNEE = 365.25


@dataclass
class Regression:
    origine:   pd.Timestamp   # t = 0
    a:         float          # ln(cours) a l'origine
    b:         float          # pente en ln par annee
    sigma:     float          # ecart-type des residus, en ln
    r2:        float
    residus:   pd.Series      # en ln, indexes par date
    debut:     pd.Timestamp
    fin:       pd.Timestamp

    def annees(self, jours) -> np.ndarray:
        return (pd.DatetimeIndex(jours) - self.origine).days.to_numpy() / ANNEE

    def droite(self, jours, k: float = 0.0) -> np.ndarray:
        return np.exp(self.a + self.b * self.annees(jours) + k * self.sigma)

    @property
    def pente(self) -> float:
        """Croissance annuelle moyenne de la tendance."""
        return float(np.exp(self.b) - 1)

    @property
    def ecart_type(self) -> float:
        """Largeur d'un ecart-type, en pourcentage du cours de tendance."""
        return float(np.exp(self.sigma) - 1)

    @property
    def position(self) -> float:
        """Dernier cours, en nombre d'ecarts-types au-dessus (+) ou en dessous (-) de la droite."""
        return float(self.residus.iloc[-1] / self.sigma) if self.sigma > 0 else 0.0

    @property
    def retour_droite(self) -> float:
        """Gain (ou perte) si le cours revenait aujourd'hui sur sa droite."""
        return float(np.exp(-self.residus.iloc[-1]) - 1)

    def repartition(self) -> dict[str, float]:
        z = self.residus / self.sigma if self.sigma > 0 else self.residus * 0
        return {cle: float(((z >= bas) & (z < haut)).mean())
                for (bas, cle, _), haut in zip(ZONES, [b for b, _, _ in ZONES[1:]] + [np.inf])}


def zone(position: float) -> tuple[str, str]:
    cle, libelle = ZONES[0][1], ZONES[0][2]
    for bas, c, l in ZONES:
        if position >= bas:
            cle, libelle = c, l
    return cle, libelle


def ajuster(cours: pd.Series) -> Regression | None:
    """Moindres carres de ln(cours) sur le temps (en annees)."""
    cours = cours[cours > 0].dropna()
    if len(cours) < 30:
        return None

    origine = cours.index[0]
    t = (cours.index - origine).days.to_numpy() / ANNEE
    y = np.log(cours.to_numpy())
    b, a = np.polyfit(t, y, 1)
    residus = y - (a + b * t)
    variance_totale = float(np.var(y))
    return Regression(
        origine=origine, a=float(a), b=float(b),
        sigma=float(np.std(residus, ddof=2)),
        r2=1 - float(np.var(residus)) / variance_totale if variance_totale > 0 else 0.0,
        residus=pd.Series(residus, index=cours.index),
        debut=cours.index[0], fin=cours.index[-1],
    )
