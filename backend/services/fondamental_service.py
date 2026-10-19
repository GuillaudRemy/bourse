from fastapi import HTTPException
from sqlmodel import Session, select
from backend.db.schema import Valeur, Fondamental
from backend.models.fondamental import FondamentalEcriture, FondamentalRead


class FondamentalService:
    def __init__(self, session: Session):
        self._db = session

    def list(self, valeur_id: int) -> list[FondamentalRead]:
        self._valeur(valeur_id)
        lignes = self._db.exec(
            select(Fondamental).where(Fondamental.valeur_id == valeur_id).order_by(Fondamental.annee)
        ).all()
        return [FondamentalRead.model_validate(l) for l in lignes]

    def ecrire(self, valeur_id: int, annee: int, data: FondamentalEcriture) -> FondamentalRead:
        """Cree ou remplace l'annee ; une saisie a la main devient prioritaire sur Yahoo."""
        self._valeur(valeur_id)
        if not 1900 <= annee <= 2200:
            raise HTTPException(422, "Année invalide.")
        ligne = self._db.exec(
            select(Fondamental).where(Fondamental.valeur_id == valeur_id, Fondamental.annee == annee)
        ).first() or Fondamental(valeur_id=valeur_id, annee=annee)
        for cle, v in data.model_dump().items():
            setattr(ligne, cle, v)
        ligne.source = "manuel"
        self._db.add(ligne)
        self._db.commit()
        self._db.refresh(ligne)
        return FondamentalRead.model_validate(ligne)

    def delete(self, valeur_id: int, annee: int) -> None:
        ligne = self._db.exec(
            select(Fondamental).where(Fondamental.valeur_id == valeur_id, Fondamental.annee == annee)
        ).first()
        if not ligne:
            raise HTTPException(404, "Année introuvable.")
        self._db.delete(ligne)
        self._db.commit()

    def _valeur(self, valeur_id: int) -> Valeur:
        valeur = self._db.get(Valeur, valeur_id)
        if not valeur:
            raise HTTPException(404, "Valeur introuvable.")
        return valeur
