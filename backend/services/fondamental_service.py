import json

from fastapi import HTTPException
from sqlmodel import Session, select

from backend.db.schema import Fondamental, Valeur
from backend.models.fondamental import FondamentalEcriture, FondamentalRead
from backend.services import cache
from backend.services.stockage import charger_fondamentaux, provenance


class FondamentalService:
    def __init__(self, session: Session):
        self._db = session

    def list(self, valeur_id: int) -> list[FondamentalRead]:
        self._valeur(valeur_id)
        return [FondamentalRead(**f) for f in charger_fondamentaux(self._db, valeur_id)]

    def ecrire(self, valeur_id: int, annee: int, data: FondamentalEcriture) -> FondamentalRead:
        """Modifie les postes envoyes (et eux seuls) : ils deviennent des saisies manuelles,
        que plus aucune actualisation n'ecrasera. Envoyer null efface la case et la protege."""
        self._valeur(valeur_id)
        cache.invalider(valeur_id)
        if not 1900 <= annee <= 2200:
            raise HTTPException(422, "Année invalide.")
        ligne = self._ligne(valeur_id, annee) or Fondamental(valeur_id=valeur_id, annee=annee, source="manuel")
        origine = provenance(ligne) if ligne.id else {}
        for cle, v in data.model_dump(exclude_unset=True).items():
            setattr(ligne, cle, v)
            origine[cle] = "manuel"
        ligne.sources = json.dumps(origine)
        if origine:
            ligne.source = "manuel"
        self._db.add(ligne)
        self._db.commit()
        return next(f for f in self.list(valeur_id) if f.annee == annee)

    def delete(self, valeur_id: int, annee: int) -> None:
        ligne = self._ligne(valeur_id, annee)
        if not ligne:
            raise HTTPException(404, "Année introuvable.")
        cache.invalider(valeur_id)
        self._db.delete(ligne)
        self._db.commit()

    def _ligne(self, valeur_id: int, annee: int) -> Fondamental | None:
        return self._db.exec(
            select(Fondamental).where(Fondamental.valeur_id == valeur_id, Fondamental.annee == annee)
        ).first()

    def _valeur(self, valeur_id: int) -> Valeur:
        valeur = self._db.get(Valeur, valeur_id)
        if not valeur:
            raise HTTPException(404, "Valeur introuvable.")
        return valeur
