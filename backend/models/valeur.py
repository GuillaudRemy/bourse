import json
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

TypeValeur = Literal["action", "indice", "etf", "matiere"]


class ValeurCreate(BaseModel):
    """Avec source « yahoo », seul le symbole compte : le reste vient de Yahoo.
    Avec source « import », la valeur est creee vide, les cours arrivent par fichier."""
    symbole: str = Field(min_length=1, max_length=30)
    source:  Literal["yahoo", "import"] = "yahoo"
    nom:     Optional[str] = Field(default=None, max_length=120)
    type:    TypeValeur = "action"
    devise:  Optional[str] = Field(default=None, max_length=10)
    isin:    Optional[str] = Field(default=None, max_length=12)   # si la valeur a ete trouvee par son ISIN


class ValeurUpdate(BaseModel):
    nom:              Optional[str] = Field(default=None, min_length=1, max_length=120)
    type:             Optional[TypeValeur] = None
    devise:           Optional[str] = Field(default=None, max_length=10)
    secteur:          Optional[str] = Field(default=None, max_length=80)
    debut_regression: Optional[date] = None
    rupture:          Optional[bool] = None
    notes:            Optional[str] = None
    isin:             Optional[str] = Field(default=None, max_length=12)
    lei:              Optional[str] = Field(default=None, max_length=20)
    cik:              Optional[str] = Field(default=None, max_length=10)
    devise_comptes:   Optional[str] = Field(default=None, max_length=10)


class ValeurRead(BaseModel):
    model_config = {"from_attributes": True}

    id:               int
    symbole:          str
    nom:              str
    type:             str
    source:           str
    devise:           Optional[str]
    place:            Optional[str]
    secteur:          Optional[str]
    pays:             Optional[str]
    isin:             Optional[str] = None
    lei:              Optional[str] = None
    cik:              Optional[str] = None
    devise_comptes:   Optional[str] = None
    debut_regression: Optional[date]
    rupture:          bool
    notes:            Optional[str]
    infos:            dict = {}
    maj_le:           Optional[datetime]

    @field_validator("infos", mode="before")
    @classmethod
    def lire_infos(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v or {}


class Resultat(BaseModel):
    """Retour d'une actualisation ou d'un import."""
    message: str
    cours:        int = 0
    fondamentaux: int = 0
    avertissements: list[str] = []
