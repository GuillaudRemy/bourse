from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.db.db import get_session
from backend.models.fondamental import FondamentalEcriture, FondamentalRead
from backend.services.fondamental_service import FondamentalService

router = APIRouter(tags=["Fondamentaux"], prefix="/valeurs/{valeur_id}/fondamentaux")


def get_service(session: Session = Depends(get_session)) -> FondamentalService:
    return FondamentalService(session=session)


@router.get("", response_model=list[FondamentalRead])
def list_fondamentaux(valeur_id: int, service: FondamentalService = Depends(get_service)):
    return service.list(valeur_id)


@router.put("/{annee}", response_model=FondamentalRead)
def ecrire_fondamental(
    valeur_id: int, annee: int, data: FondamentalEcriture,
    service: FondamentalService = Depends(get_service),
):
    return service.ecrire(valeur_id, annee, data)


@router.delete("/{annee}", status_code=204)
def delete_fondamental(valeur_id: int, annee: int, service: FondamentalService = Depends(get_service)):
    service.delete(valeur_id, annee)
