from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from backend.db.db import get_session
from backend.models.portefeuille import CompteEcriture, CompteRead, TransactionEcriture, TransactionRead
from backend.services import releve_service
from backend.services.portefeuille_service import PortefeuilleService

router = APIRouter(tags=["Portefeuille"], prefix="/portefeuille")


def get_service(session: Session = Depends(get_session)) -> PortefeuilleService:
    return PortefeuilleService(session=session)


@router.get("")
def synthese(compte_id: Optional[int] = None, service: PortefeuilleService = Depends(get_service)):
    """Positions, performance, risque, repartition et fiscalite (d'un compte, ou de tous)."""
    return service.synthese(compte_id)


@router.get("/comptes", response_model=list[CompteRead])
def comptes(service: PortefeuilleService = Depends(get_service)):
    return service.comptes()


@router.post("/comptes", response_model=CompteRead, status_code=201)
def creer_compte(data: CompteEcriture, service: PortefeuilleService = Depends(get_service)):
    return service.ecrire_compte(data)


@router.put("/comptes/{compte_id}", response_model=CompteRead)
def modifier_compte(compte_id: int, data: CompteEcriture, service: PortefeuilleService = Depends(get_service)):
    return service.ecrire_compte(data, compte_id)


@router.delete("/comptes/{compte_id}", status_code=204)
def supprimer_compte(compte_id: int, service: PortefeuilleService = Depends(get_service)):
    service.supprimer_compte(compte_id)


@router.get("/transactions", response_model=list[TransactionRead])
def transactions(compte_id: Optional[int] = None, service: PortefeuilleService = Depends(get_service)):
    return service.transactions(compte_id)


@router.post("/transactions", response_model=TransactionRead, status_code=201)
def creer_transaction(data: TransactionEcriture, service: PortefeuilleService = Depends(get_service)):
    return service.ecrire_transaction(data)


@router.put("/transactions/{transaction_id}", response_model=TransactionRead)
def modifier_transaction(transaction_id: int, data: TransactionEcriture, service: PortefeuilleService = Depends(get_service)):
    return service.ecrire_transaction(data, transaction_id)


@router.delete("/transactions/{transaction_id}", status_code=204)
def supprimer_transaction(transaction_id: int, service: PortefeuilleService = Depends(get_service)):
    service.supprimer_transaction(transaction_id)


@router.post("/comptes/{compte_id}/releve")
async def lire_releve(compte_id: int, fichier: UploadFile = File(...), db: Session = Depends(get_session)):
    """Proposition d'operations lues dans un releve de courtier (rien n'est enregistre)."""
    PortefeuilleService(db)._compte(compte_id)
    return releve_service.proposer(db, compte_id, await fichier.read())


class Lignes(BaseModel):
    lignes: list[dict]


@router.post("/comptes/{compte_id}/releve/valider")
def valider_releve(compte_id: int, data: Lignes, db: Session = Depends(get_session)):
    PortefeuilleService(db)._compte(compte_id)
    return releve_service.valider(db, compte_id, data.lignes)
