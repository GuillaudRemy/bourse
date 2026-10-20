from typing import Optional

from pydantic import BaseModel, Field


class FondamentalEcriture(BaseModel):
    bpa:              Optional[float] = None
    benefice_net:     Optional[float] = None
    chiffre_affaires: Optional[float] = None
    dividende:        Optional[float] = None


class FondamentalRead(FondamentalEcriture):
    model_config = {"from_attributes": True}

    annee:  int = Field(ge=1900, le=2200)
    source: str
    per:    Optional[float] = None   # cours moyen de l'annee / BPA
