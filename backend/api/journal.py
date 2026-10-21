from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from backend.db.db import get_session
from backend.models.journal import DecisionEcriture, DecisionRead, PieceRead, TheseEcriture, TheseRead
from backend.services.journal_service import JournalService

router = APIRouter(tags=["Journal"], prefix="/valeurs/{valeur_id}/journal")


def get_service(session: Session = Depends(get_session)) -> JournalService:
    return JournalService(session=session)


@router.get("/these", response_model=TheseRead)
def lire_these(valeur_id: int, service: JournalService = Depends(get_service)):
    return service.these(valeur_id)


@router.put("/these", response_model=TheseRead)
def ecrire_these(valeur_id: int, data: TheseEcriture, service: JournalService = Depends(get_service)):
    return service.ecrire_these(valeur_id, data)


@router.get("/decisions", response_model=list[DecisionRead])
def decisions(valeur_id: int, service: JournalService = Depends(get_service)):
    return service.decisions(valeur_id)


@router.post("/decisions", response_model=DecisionRead, status_code=201)
def ajouter_decision(valeur_id: int, data: DecisionEcriture, service: JournalService = Depends(get_service)):
    return service.ecrire_decision(valeur_id, data)


@router.put("/decisions/{decision_id}", response_model=DecisionRead)
def modifier_decision(valeur_id: int, decision_id: int, data: DecisionEcriture,
                      service: JournalService = Depends(get_service)):
    return service.ecrire_decision(valeur_id, data, decision_id)


@router.delete("/decisions/{decision_id}", status_code=204)
def supprimer_decision(valeur_id: int, decision_id: int, service: JournalService = Depends(get_service)):
    service.supprimer_decision(valeur_id, decision_id)


@router.get("/pieces", response_model=list[PieceRead])
def pieces(valeur_id: int, service: JournalService = Depends(get_service)):
    return service.pieces(valeur_id)


@router.post("/pieces", response_model=PieceRead, status_code=201)
async def ajouter_piece(valeur_id: int, fichier: UploadFile = File(...), service: JournalService = Depends(get_service)):
    return await service.ajouter_piece(valeur_id, fichier)


@router.get("/pieces/{piece_id}")
def telecharger_piece(valeur_id: int, piece_id: int, service: JournalService = Depends(get_service)):
    chemin, p = service.piece(valeur_id, piece_id)
    return FileResponse(chemin, media_type=p.type_mime, filename=p.nom, content_disposition_type="inline")


@router.delete("/pieces/{piece_id}", status_code=204)
def supprimer_piece(valeur_id: int, piece_id: int, service: JournalService = Depends(get_service)):
    service.supprimer_piece(valeur_id, piece_id)
