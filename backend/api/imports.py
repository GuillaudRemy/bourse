from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from backend.db.champs import PAR_CLE
from backend.db.db import get_session
from backend.db.schema import Valeur
from backend.models.valeur import Resultat
from backend.services import import_service, pdf_service
from backend.services.stockage import enregistrer_fondamentaux
from backend.sources.xbrl import signe

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


class Texte(BaseModel):
    texte: str


@router.post("/fondamentaux/texte", response_model=Resultat)
def coller_fondamentaux(valeur_id: int, data: Texte, db: Session = Depends(get_session)):
    """Tableau colle depuis un tableur (Excel, LibreOffice, Google Sheets) : tabulations."""
    return import_service.importer_fondamentaux(db, _valeur(db, valeur_id), data.texte.encode("utf-8"))


@router.post("/pdf")
async def lire_pdf(valeur_id: int, fichier: UploadFile = File(...), db: Session = Depends(get_session)):
    """Proposition extraite d'un rapport annuel PDF ; rien n'est enregistre avant validation."""
    _valeur(db, valeur_id)
    return pdf_service.analyser_pdf(await _lire(fichier))


class Lot(BaseModel):
    annees: dict[int, dict[str, float | None]]
    source: Literal["pdf", "import", "manuel"] = "pdf"


@router.post("/lot", response_model=Resultat)
def enregistrer_lot(valeur_id: int, data: Lot, db: Session = Depends(get_session)):
    """Comptes valides par l'utilisateur (apres relecture d'une extraction PDF)."""
    _valeur(db, valeur_id)
    annees = {a: {c: signe(c, v) for c, v in postes.items() if c in PAR_CLE and v is not None}
              for a, postes in data.annees.items()}
    nombre = enregistrer_fondamentaux(db, valeur_id, annees, data.source)
    db.commit()
    return Resultat(message=f"{nombre} année(s) enregistrée(s).", fondamentaux=nombre)
