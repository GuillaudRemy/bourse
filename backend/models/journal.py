from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# Questions a se poser avant d'acheter, reprises de la methode (video) et de l'investissement « qualite ».
CHECKLIST = [
    "La droite couvre-t-elle au moins 20 ans (plusieurs cycles) ?",
    "La pente est-elle portée par la croissance des bénéfices, pas par un PER qui gonfle ?",
    "L'entreprise est-elle restée fidèle à elle-même (pas de rupture de modèle) ?",
    "A-t-elle un avantage concurrentiel durable (marque, coûts, réseau, brevets) ?",
    "Ce que je sais faire : est-ce que je comprends comment elle gagne de l'argent ?",
    "La dette est-elle raisonnable (dette nette < 2 à 3 ans d'EBITDA) ?",
    "Les bénéfices se retrouvent-ils en trésorerie (free cash flow) ?",
    "Le cours est-il sous sa droite, ou au moins pas tout en haut du couloir ?",
    "Les dirigeants sont-ils dignes de confiance (pas de dilution, de scandale) ?",
    "Ai-je écrit ce qui me ferait vendre ?",
]

TypeDecision = Literal["achat", "renforcement", "allegement", "vente", "attente"]
Reponse = Literal["oui", "non", "?"]


class TheseEcriture(BaseModel):
    pourquoi:   Optional[str] = None
    avantage:   Optional[str] = None
    risques:    Optional[str] = None
    prix_achat: Optional[float] = None
    prix_vente: Optional[float] = None
    conditions: Optional[str] = None
    checklist:  dict[str, Reponse] = {}


class TheseRead(TheseEcriture):
    maj_le:    Optional[datetime] = None
    questions: list[str] = CHECKLIST


class DecisionEcriture(BaseModel):
    jour:      date
    type:      TypeDecision
    prix:      Optional[float] = None
    raison:    Optional[str] = Field(default=None, max_length=5000)
    relecture: Optional[str] = Field(default=None, max_length=5000)
    verdict:   Optional[Literal["bonne", "mauvaise", "neutre"]] = None


class DecisionRead(DecisionEcriture):
    model_config = {"from_attributes": True}
    id: int


class PieceRead(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    nom: str
    type_mime: str
    taille: int
    created_at: datetime
