from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

TypeCompte = Literal["PEA", "PEA-PME", "CTO", "AV", "autre"]
TypeTransaction = Literal["achat", "vente", "dividende", "frais", "depot", "retrait", "division"]


class CompteEcriture(BaseModel):
    nom:       str = Field(min_length=1, max_length=80)
    type:      TypeCompte = "CTO"
    ouverture: Optional[date] = None
    courtier:  Optional[str] = Field(default=None, max_length=80)
    # Grille de frais du courtier ; vide = reglages par defaut. `frais_pct` en fraction (0,001 = 0,1 %).
    frais_fixe: Optional[float] = Field(default=None, ge=0)
    frais_pct:  Optional[float] = Field(default=None, ge=0, le=0.1)
    frais_min:  Optional[float] = Field(default=None, ge=0)


class CompteRead(CompteEcriture):
    model_config = {"from_attributes": True}
    id: int


class TransactionEcriture(BaseModel):
    """`montant` (EUR) est calcule s'il manque : quantite x prix x taux de change -/+ frais.
    `frais` vide sur un achat ou une vente : calcules (courtage du compte + TTF le cas echeant)."""
    compte_id: int
    valeur_id: Optional[int] = None
    jour:      date
    type:      TypeTransaction
    quantite:  Optional[float] = Field(default=None, ge=0)
    prix:      Optional[float] = Field(default=None, ge=0)
    frais:     Optional[float] = Field(default=None, ge=0)
    montant:   Optional[float] = None
    note:      Optional[str] = Field(default=None, max_length=500)


class TransactionRead(TransactionEcriture):
    model_config = {"from_attributes": True}
    id: int
    frais: float = 0.0
    ttf:   float = 0.0
