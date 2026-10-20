from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from backend.db.db import get_session
from backend.models.valeur import Resultat, ValeurCreate, ValeurRead, ValeurUpdate
from backend.services.analyse_service import AnalyseService
from backend.services.valeur_service import ValeurService
from backend.sources import yahoo

router = APIRouter(tags=["Valeurs"], prefix="/valeurs")


def get_service(session: Session = Depends(get_session)) -> ValeurService:
    return ValeurService(session=session)


def get_analyse(session: Session = Depends(get_session)) -> AnalyseService:
    return AnalyseService(session=session)


@router.get("/recherche")
def rechercher(q: str = Query(min_length=1)):
    """Recherche d'un symbole chez Yahoo (« air liquide », « AAPL », « CAC 40 »…)."""
    try:
        return yahoo.rechercher(q)
    except yahoo.SourceIndisponible as e:
        raise HTTPException(502, str(e)) from e


@router.get("", response_model=list[ValeurRead])
def list_valeurs(service: ValeurService = Depends(get_service)):
    return service.list()


@router.get("/synthese")
def synthese(analyse: AnalyseService = Depends(get_analyse)):
    return analyse.synthese()


@router.post("", response_model=ValeurRead, status_code=201)
def create_valeur(data: ValeurCreate, service: ValeurService = Depends(get_service)):
    return service.create(data)


@router.post("/actualiser", response_model=Resultat)
def actualiser_tout(service: ValeurService = Depends(get_service)):
    return service.actualiser_tout()


@router.get("/{valeur_id}", response_model=ValeurRead)
def get_valeur(valeur_id: int, service: ValeurService = Depends(get_service)):
    return service.get(valeur_id)


@router.get("/{valeur_id}/analyse")
def analyse_valeur(
    valeur_id: int,
    dividendes: bool = True,
    debut: Optional[date] = None,
    en_euros: bool = False,
    analyse: AnalyseService = Depends(get_analyse),
):
    return analyse.analyse(valeur_id, dividendes, debut, en_euros)


@router.patch("/{valeur_id}", response_model=ValeurRead)
def update_valeur(valeur_id: int, data: ValeurUpdate, service: ValeurService = Depends(get_service)):
    return service.update(valeur_id, data)


@router.post("/{valeur_id}/actualiser", response_model=Resultat)
def actualiser(valeur_id: int, service: ValeurService = Depends(get_service)):
    return service.actualiser(valeur_id)


@router.delete("/{valeur_id}", status_code=204)
def delete_valeur(valeur_id: int, service: ValeurService = Depends(get_service)):
    service.delete(valeur_id)
