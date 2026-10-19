from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session
from backend.db.db import get_session
from backend.db.schema import Valeur
from backend.models.valeur import Resultat
from backend.services import import_service

router = APIRouter(tags=["Imports"], prefix="/valeurs/{valeur_id}/import")

TAILLE_MAX = 20 * 1024 * 1024


async def _lire(fichier: UploadFile) -> bytes:
    contenu = await fichier.read()
    if len(contenu) > TAILLE_MAX:
        raise HTTPException(413, "Fichier trop volumineux (20 Mo maximum).")
    return contenu


def _valeur(db: Session, valeur_id: int) -> Valeur:
    valeur = db.get(Valeur, valeur_id)
    if not valeur:
        raise HTTPException(404, "Valeur introuvable.")
    return valeur


@router.post("/cours", response_model=Resultat)
async def importer_cours(
    valeur_id: int, fichier: UploadFile = File(...), db: Session = Depends(get_session),
):
    return import_service.importer_cours(db, _valeur(db, valeur_id), await _lire(fichier))


@router.post("/fondamentaux", response_model=Resultat)
async def importer_fondamentaux(
    valeur_id: int, fichier: UploadFile = File(...), db: Session = Depends(get_session),
):
    return import_service.importer_fondamentaux(db, _valeur(db, valeur_id), await _lire(fichier))
