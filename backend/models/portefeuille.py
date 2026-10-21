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


class CompteRead(CompteEcriture):
    model_config = {"from_attributes": True}
    id: int


class TransactionEcriture(BaseModel):
    """`montant` (EUR) est calcule s'il manque : quantite x prix x taux de change -/+ frais."""
    compte_id: int
    valeur_id: Optional[int] = None
    jour:      date
    type:      TypeTransaction
    quantite:  Optional[float] = Field(default=None, ge=0)
    prix:      Optional[float] = Field(default=None, ge=0)
    frais:     float = Field(default=0.0, ge=0)
    montant:   Optional[float] = None
    note:      Optional[str] = Field(default=None, max_length=500)


class TransactionRead(TransactionEcriture):
    model_config = {"from_attributes": True}
    id: int
