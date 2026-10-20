from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlmodel import Session, select

from backend.db.schema import Valeur
from backend.models.valeur import Resultat, ValeurCreate, ValeurRead, ValeurUpdate
from backend.services.stockage import (
    charger_divisions,
    enregistrer_cours,
    enregistrer_divisions,
    enregistrer_fondamentaux,
)
from backend.sources import esef, sec, yahoo, yahoo_direct
from backend.sources.base import Identite, SourceIndisponible


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
            except SourceIndisponible as e:
                raise HTTPException(502, str(e)) from e
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
        """Met a jour cours, divisions, fiche et comptes depuis toutes les sources utiles.

        Les cours sont retelecharges en entier : le cours ajuste change retroactivement a
        chaque dividende. Chaque etape a un secours ; une source en panne n'empeche pas les
        autres de passer, elle est simplement signalee dans le message."""
        valeur = self._get(valeur_id)
        avertissements: list[str] = []
        nb_cours = 0

        if valeur.source == "yahoo":
            cours = self._premier_disponible(
                [lambda: yahoo.cours(valeur.symbole), lambda: yahoo_direct.cours(valeur.symbole)], avertissements)
            if cours is None or cours.empty:
                raise HTTPException(502, "Cours indisponibles : " + " · ".join(avertissements))
            nb_cours = enregistrer_cours(self._db, valeur.id, cours)

            divisions = self._premier_disponible(
                [lambda: yahoo.divisions(valeur.symbole), lambda: yahoo_direct.divisions(valeur.symbole)],
                avertissements)
            if divisions is not None:
                enregistrer_divisions(self._db, valeur.id, divisions)

            try:
                fiche = yahoo.fiche(valeur.symbole)
                valeur.infos = json.dumps(fiche.infos)
                valeur.devise = valeur.devise or fiche.devise
                valeur.secteur = valeur.secteur or fiche.secteur
                valeur.pays = valeur.pays or fiche.pays
                valeur.devise_comptes = valeur.devise_comptes or fiche.devise_comptes
            except SourceIndisponible as e:
                avertissements.append(str(e))
        self._db.flush()

        nb_fond, sources = self._actualiser_comptes(valeur, avertissements)
        valeur.maj_le = datetime.now(UTC)
        self._db.commit()

        message = f"{valeur.nom} : {nb_cours} séances, {nb_fond} années de comptes"
        message += f" ({', '.join(sources)})." if sources else "."
        if avertissements:
            message += " " + " · ".join(avertissements)
        return Resultat(message=message, cours=nb_cours, fondamentaux=nb_fond, avertissements=avertissements)

    def _actualiser_comptes(self, valeur: Valeur, avertissements: list[str]) -> tuple[int, list[str]]:
        if valeur.type != "action":
            return 0, []
        identite = Identite(symbole=valeur.symbole, nom=valeur.nom, type=valeur.type, pays=valeur.pays,
                            isin=valeur.isin, lei=valeur.lei, cik=valeur.cik)
        divisions = charger_divisions(self._db, valeur.id)
        annees: set[int] = set()
        utilisees = []
        # Du moins fiable au plus fiable : la fusion case par case garde la meilleure source.
        etapes = [("yahoo", lambda: yahoo.comptes(identite))] if valeur.source == "yahoo" else []
        etapes += [(module.NOM, lambda m=module: m.comptes(identite, divisions))
                   for module in (esef, sec) if module.couvre(identite)]
        for nom, appel in etapes:
            try:
                comptes = appel()
            except SourceIndisponible as e:
                avertissements.append(str(e))
                continue
            if comptes:
                enregistrer_fondamentaux(self._db, valeur.id, comptes, nom)
                annees |= set(comptes)
                utilisees.append(nom.upper() if nom != "yahoo" else "Yahoo")

        for cle in ("lei", "cik", "devise_comptes"):
            if identite.decouverts.get(cle) and not getattr(valeur, cle):
                setattr(valeur, cle, identite.decouverts[cle])
        return len(annees), utilisees

    @staticmethod
    def _premier_disponible(appels, avertissements: list[str]):
        """Essaie chaque source dans l'ordre ; la premiere qui repond l'emporte."""
        for appel in appels:
            try:
                resultat = appel()
            except SourceIndisponible as e:
                avertissements.append(str(e))
                continue
            if resultat is not None and len(resultat):
                return resultat
        return None

    def actualiser_tout(self) -> Resultat:
        valeurs = self._db.exec(select(Valeur)).all()
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
