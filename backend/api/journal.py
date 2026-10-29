import json
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, col, select

from backend.db.db import get_session
from backend.db.schema import Annotation, Valeur
from backend.models.journal import DecisionEcriture, DecisionRead, PieceRead, TheseEcriture, TheseRead
from backend.services.journal_service import JournalService

router = APIRouter(tags=["Journal"], prefix="/valeurs/{valeur_id}/journal")
annotations = APIRouter(tags=["Journal"], prefix="/valeurs/{valeur_id}/annotations")


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


# ── Annotations des graphiques (niveaux, lignes de tendance, notes) ──
class AnnotationEcriture(BaseModel):
    type: Literal["niveau", "ligne", "note"]
    donnees: dict


def _annotation(a: Annotation) -> dict:
    return {"id": a.id, "type": a.type, "donnees": json.loads(a.donnees)}


@annotations.get("")
def lire_annotations(valeur_id: int, db: Session = Depends(get_session)):
    requete = select(Annotation).where(Annotation.valeur_id == valeur_id).order_by(col(Annotation.id))
    return [_annotation(a) for a in db.exec(requete)]


@annotations.post("", status_code=201)
def creer_annotation(valeur_id: int, data: AnnotationEcriture, db: Session = Depends(get_session)):
    if not db.get(Valeur, valeur_id):
        raise HTTPException(404, "Valeur introuvable.")
    a = Annotation(valeur_id=valeur_id, type=data.type, donnees=json.dumps(data.donnees, ensure_ascii=False))
    db.add(a)
    db.commit()
    db.refresh(a)
    return _annotation(a)


@annotations.delete("/{annotation_id}", status_code=204)
def supprimer_annotation(valeur_id: int, annotation_id: int, db: Session = Depends(get_session)):
    a = db.get(Annotation, annotation_id)
    if not a or a.valeur_id != valeur_id:
        raise HTTPException(404, "Annotation introuvable.")
    db.delete(a)
    db.commit()
