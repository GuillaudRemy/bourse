"""Interface commune des sources de donnees.

Une source sait faire tout ou partie de : fournir des cours, des comptes annuels, des
divisions d'actions. Elle dit d'abord si elle couvre une valeur (`couvre`), puis renvoie
des donnees dans un format commun ; c'est `stockage` qui les fusionne selon la priorite
de chaque source (champs.PRIORITE).
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

import pandas as pd

# Comptes : {annee: {cle de champs.py: valeur}}
Comptes = dict[int, dict[str, float]]


class SourceIndisponible(Exception):
    """La source ne repond pas, ne connait pas la valeur, ou n'est pas configuree."""


@dataclass
class Identite:
    """Ce qu'une source a besoin de connaitre d'une valeur pour la retrouver chez elle."""
    symbole: str
    nom: str = ""
    type: str = "action"
    pays: str | None = None
    isin: str | None = None
    lei: str | None = None
    cik: str | None = None
    # Identifiants decouverts en route (LEI, CIK), a memoriser sur la valeur.
    decouverts: dict = field(default_factory=dict)


class SourceCours(Protocol):
    nom: str

    def cours(self, symbole: str, debut: date | None = None) -> pd.DataFrame:
        """Colonnes : jour, ouverture, haut, bas, cloture, ajuste, volume."""


class SourceComptes(Protocol):
    nom: str

    def couvre(self, identite: Identite) -> bool:
        """Vrai si la source peut avoir des comptes pour cette valeur (sans appel reseau couteux)."""

    def comptes(self, identite: Identite) -> Comptes: ...
