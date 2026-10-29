"""Outils : simulateur de patrimoine."""
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.analyse.simulateur import CLASSES, Poche, simuler
from backend.db.db import get_session
from backend.db.schema import Valeur
from backend.services.analyse_service import AnalyseService
from backend.sources import catalogue

router = APIRouter(tags=["Outils"], prefix="/simulateur")


class PocheEntree(BaseModel):
    classe: str
    part: float = Field(ge=0, le=1)
    rendement: float = Field(ge=-0.5, le=0.5)
    volatilite: float = Field(ge=0, le=1.5)


class Simulation(BaseModel):
    versement: float = Field(ge=0, le=1_000_000)
    capital: float = Field(0, ge=0, le=100_000_000)
    annees: int = Field(ge=1, le=40)
    inflation: float = Field(0, ge=0, le=0.2)
    poches: list[PocheEntree]


@router.get("/classes")
def classes(db: Session = Depends(get_session)):
    """Hypotheses par defaut, et valeurs suivies pouvant servir a les mesurer."""
    valeurs = [{"id": v.id, "nom": v.nom, "type": v.type}
               for v in db.exec(select(Valeur).order_by(Valeur.nom)) if v.type not in catalogue.SANS_DROITE]
    return {"classes": CLASSES, "valeurs": valeurs}


@router.post("")
def lancer(s: Simulation):
    poches = [Poche(p.classe, p.part, p.rendement, p.volatilite) for p in s.poches if p.part > 0]
    try:
        return simuler(poches, s.versement, s.capital, s.annees, s.inflation)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/mesurer/{valeur_id}")
def mesurer(valeur_id: int, annees: int = 20, db: Session = Depends(get_session)):
    """Rendement annuel (geometrique, dividendes reinvestis, en euros) et volatilite d'une valeur suivie,
    sur ses `annees` dernieres annees : pour remplacer une hypothese par l'histoire d'un placement reel."""
    _, cours, base_ajustee, *_ = AnalyseService(db)._contexte(valeur_id, True, None, en_euros=True)
    if cours.empty:
        raise HTTPException(409, "Aucun cours pour cette valeur.")
    serie = (cours["ajuste"] if base_ajustee else cours["cloture"]).dropna()
    mensuel = serie.resample("ME").last().dropna()
    mensuel = mensuel[mensuel.index >= mensuel.index[-1] - np.timedelta64(annees * 365, "D")]
    if len(mensuel) < 37:
        raise HTTPException(409, "Moins de 3 ans d'historique : mesure trop fragile.")
    rendements = np.log(mensuel).diff().dropna()
    return {
        "rendement": float(np.exp(rendements.mean() * 12) - 1),
        "volatilite": float(rendements.std() * np.sqrt(12)),
        "debut": mensuel.index[0].strftime("%Y-%m-%d"), "fin": mensuel.index[-1].strftime("%Y-%m-%d"),
        "dividendes": base_ajustee,
    }
