from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core import reglages
from backend.db.champs import catalogue

router = APIRouter(tags=["Reglages"])


class Ecriture(BaseModel):
    valeur: str | None = None


@router.get("/champs")
def champs():
    """Postes des etats financiers : cle, libelle, etat, unite, aide."""
    return catalogue()


@router.get("/reglages")
def lire_reglages():
    return reglages.tous()


@router.put("/reglages/{cle}")
def ecrire_reglage(cle: str, data: Ecriture):
    if cle not in reglages.PAR_CLE:
        raise HTTPException(404, "Réglage inconnu.")
    if cle == "valeurs_par_page" and (data.valeur or "").strip() not in ("20", "50", "100"):
        raise HTTPException(422, "Choisissez 20, 50 ou 100 valeurs par page.")
    reglages.ecrire(cle, data.valeur)
    return reglages.tous()
