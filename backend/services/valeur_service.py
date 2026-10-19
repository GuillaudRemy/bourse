import json
from datetime import datetime, UTC
from fastapi import HTTPException
from sqlmodel import Session, select
from backend.db.schema import Valeur
from backend.models.valeur import ValeurCreate, ValeurUpdate, ValeurRead, Resultat
from backend.services.stockage import enregistrer_cours, enregistrer_fondamentaux
from backend.sources import yahoo


class ValeurService:
    def __init__(self, session: Session):
        self._db = session

    def list(self) -> list[ValeurRead]:
        valeurs = self._db.exec(select(Valeur).order_by(Valeur.type, Valeur.nom)).all()
        return [ValeurRead.model_validate(v) for v in valeurs]

    def get(self, valeur_id: int) -> ValeurRead:
        return ValeurRead.model_validate(self._get(valeur_id))

    def create(self, data: ValeurCreate) -> ValeurRead:
        symbole = data.symbole.strip().upper()
        if self._db.exec(select(Valeur).where(Valeur.symbole == symbole)).first():
            raise HTTPException(409, f"La valeur « {symbole} » est déjà suivie.")

        if data.source == "yahoo":
            try:
                fiche = yahoo.fiche(symbole)
            except yahoo.SourceIndisponible as e:
                raise HTTPException(502, str(e))
            valeur = Valeur(
                symbole=symbole, source="yahoo", nom=data.nom or fiche.nom, type=fiche.type,
                devise=fiche.devise, place=fiche.place, secteur=fiche.secteur, pays=fiche.pays,
                infos=json.dumps(fiche.infos),
            )
        else:
            valeur = Valeur(
                symbole=symbole, source="import", nom=(data.nom or symbole).strip(),
                type=data.type, devise=data.devise,
            )

        self._db.add(valeur)
        self._db.commit()
        self._db.refresh(valeur)

        if valeur.source == "yahoo":
            self.actualiser(valeur.id)
        return self.get(valeur.id)

    def update(self, valeur_id: int, data: ValeurUpdate) -> ValeurRead:
        valeur = self._get(valeur_id)
        for cle, v in data.model_dump(exclude_unset=True).items():
            if isinstance(v, str):
                v = v.strip() or None
            if cle == "nom" and not v:
                continue
            setattr(valeur, cle, v)
        self._db.commit()
        self._db.refresh(valeur)
        return ValeurRead.model_validate(valeur)

    def delete(self, valeur_id: int) -> None:
        """Supprime la valeur et, en cascade, ses cours et ses fondamentaux."""
        self._db.delete(self._get(valeur_id))
        self._db.commit()

    def actualiser(self, valeur_id: int) -> Resultat:
        """Retelecharge tout l'historique : le cours ajuste change retroactivement
        a chaque dividende, une simple mise a jour des derniers jours ne suffit pas."""
        valeur = self._get(valeur_id)
        if valeur.source != "yahoo":
            raise HTTPException(400, "Valeur importée : mettez-la à jour en important un nouveau fichier.")

        try:
            cours = yahoo.cours(valeur.symbole)
            fondamentaux = yahoo.fondamentaux(valeur.symbole)
            fiche = yahoo.fiche(valeur.symbole)
        except yahoo.SourceIndisponible as e:
            raise HTTPException(502, str(e))
        if cours.empty:
            raise HTTPException(502, f"Yahoo ne renvoie aucun cours pour {valeur.symbole}.")

        nb_cours = enregistrer_cours(self._db, valeur.id, cours)
        nb_fond = enregistrer_fondamentaux(self._db, valeur.id, fondamentaux, "yahoo", ecraser=False)
        valeur.infos = json.dumps(fiche.infos)
        valeur.devise = valeur.devise or fiche.devise
        valeur.secteur = valeur.secteur or fiche.secteur
        valeur.maj_le = datetime.now(UTC)
        self._db.commit()
        return Resultat(
            message=f"{valeur.nom} : {nb_cours} séances, {nb_fond} années de fondamentaux.",
            cours=nb_cours, fondamentaux=nb_fond,
        )

    def actualiser_tout(self) -> Resultat:
        valeurs = self._db.exec(select(Valeur).where(Valeur.source == "yahoo")).all()
        echecs = []
        for valeur in valeurs:
            try:
                self.actualiser(valeur.id)
            except HTTPException:
                self._db.rollback()
                echecs.append(valeur.symbole)
        message = f"{len(valeurs) - len(echecs)} valeur(s) actualisée(s)."
        if echecs:
            message += f" Échec : {', '.join(echecs)}."
        return Resultat(message=message)

    def _get(self, valeur_id: int) -> Valeur:
        valeur = self._db.get(Valeur, valeur_id)
        if not valeur:
            raise HTTPException(404, "Valeur introuvable.")
        return valeur
