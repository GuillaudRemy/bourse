"""Assistant local (Ollama) : etat, lecture de rapport annuel, questions sur la fiche, actualites."""
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session

from backend.db.db import get_session
from backend.services import assistant_service as assistant
from backend.services.journal_service import JournalService

router = APIRouter(tags=["Assistant"])


class Question(BaseModel):
    question: str
    historique: list[dict] = []


@router.get("/assistant")
def etat():
    return assistant.etat()


@router.get("/assistant/travaux/{travail_id}")
def travail(travail_id: str):
    return assistant.travail(travail_id)


@router.get("/valeurs/{valeur_id}/assistant")
def analyses(valeur_id: int, db: Session = Depends(get_session)):
    return assistant.analyses(db, valeur_id)


@router.delete("/valeurs/{valeur_id}/assistant/{analyse_id}", status_code=204)
def supprimer(valeur_id: int, analyse_id: int, db: Session = Depends(get_session)):
    assistant.supprimer(db, valeur_id, analyse_id)


@router.post("/valeurs/{valeur_id}/assistant/rapport")
async def lire_rapport(valeur_id: int, fichier: UploadFile = File(...), db: Session = Depends(get_session)):
    """Le PDF est aussi range dans les pieces jointes du journal, pour s'y reporter (pages citees)."""
    contenu = await fichier.read()
    await fichier.seek(0)
    await JournalService(db).ajouter_piece(valeur_id, fichier)
    return {"travail": assistant.lancer_rapport(db, valeur_id, fichier.filename or "rapport.pdf", contenu)}


@router.post("/valeurs/{valeur_id}/assistant/rapport/{piece_id}")
def relire_piece(valeur_id: int, piece_id: int, db: Session = Depends(get_session)):
    chemin, piece = JournalService(db).piece(valeur_id, piece_id)
    return {"travail": assistant.lancer_rapport(db, valeur_id, piece.nom, chemin.read_bytes())}


@router.post("/valeurs/{valeur_id}/assistant/question")
def question(valeur_id: int, data: Question, db: Session = Depends(get_session)):
    morceaux = assistant.repondre(db, valeur_id, data.question, data.historique)
    return StreamingResponse(morceaux, media_type="text/plain; charset=utf-8")


@router.post("/valeurs/{valeur_id}/assistant/actualites")
def actualites(valeur_id: int, db: Session = Depends(get_session)):
    return assistant.resumer_actualites(db, valeur_id)
