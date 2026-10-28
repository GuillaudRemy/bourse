from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlmodel import Session, col, select

from backend.db.schema import Transaction, Valeur
from backend.models.valeur import Resultat, ValeurCreate, ValeurRead, ValeurUpdate
from backend.services import alertes_service, cache
from backend.services.stockage import (
    charger_divisions,
    dernier_taux,
    enregistrer_cours,
    enregistrer_divisions,
    enregistrer_evenements,
    enregistrer_fondamentaux,
    enregistrer_taux,
)
from backend.sources import bce, esef, matieres, sec, yahoo, yahoo_direct
from backend.sources.base import Identite, SourceIndisponible


class ValeurService:
    def __init__(self, session: Session):
        self._db = session

    def list(self) -> list[ValeurRead]:
        valeurs = self._db.exec(select(Valeur).order_by(Valeur.type, Valeur.nom)).all()
        return [ValeurRead.model_validate(v) for v in valeurs]

    def get(self, valeur_id: int) -> ValeurRead:
        return ValeurRead.model_validate(self._get(valeur_id))

    def create(self, data: ValeurCreate, actualiser: bool = True) -> ValeurRead:
        """`actualiser=False` : la valeur est creee tout de suite, ses donnees viendront de
        l'actualisation en tache de fond (premier lancement : pas d'attente)."""
        symbole = data.symbole.strip().upper()
        if self._db.exec(select(Valeur).where(Valeur.symbole == symbole)).first():
            raise HTTPException(409, f"La valeur « {symbole} » est déjà suivie.")

        if data.source == "yahoo":
            try:
                fiche = yahoo.fiche(symbole)
            except SourceIndisponible as e:
                raise HTTPException(502, str(e)) from e
            valeur = Valeur(
                # Matiere premiere : nom francais du catalogue plutot que l'echeance (« Gold Dec 26 »).
                symbole=symbole, source="yahoo", nom=data.nom or matieres.nom(symbole) or fiche.nom, type=fiche.type,
                devise=fiche.devise, place=fiche.place, secteur=fiche.secteur, pays=fiche.pays,
                infos=json.dumps(fiche.infos), isin=(data.isin or "").upper() or None,
            )
        else:
            valeur = Valeur(
                symbole=symbole, source="import", nom=(data.nom or symbole).strip(),
                type=data.type, devise=data.devise,
            )

        self._db.add(valeur)
        self._db.commit()
        self._db.refresh(valeur)
        alertes_service.creer_par_defaut(self._db, valeur)
        self._db.commit()

        if valeur.source == "yahoo" and actualiser:
            self.actualiser(valeur.id)
        return self.get(valeur.id)

    def update(self, valeur_id: int, data: ValeurUpdate) -> ValeurRead:
        valeur = self._get(valeur_id)
        cache.invalider(valeur_id)
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
        cache.invalider(valeur_id)
        self._db.delete(self._get(valeur_id))
        self._db.commit()

    def supprimer_plusieurs(self, ids: list[int], confirmer: bool) -> dict:
        """Suppression groupee depuis le tableau des valeurs. Les operations du portefeuille portant
        sur ces valeurs sont conservees (historique, fiscalite) mais perdent leur lien : on le dit avant."""
        valeurs = [v for v in self._db.exec(select(Valeur).where(col(Valeur.id).in_(ids)))]
        operations = len(list(self._db.exec(select(Transaction).where(col(Transaction.valeur_id).in_(ids)))))
        if not confirmer:
            return {"noms": sorted(v.nom for v in valeurs), "operations": operations}
        for v in valeurs:
            self._db.delete(v)
        self._db.commit()
        cache.invalider()
        return {"supprimees": len(valeurs), "operations": operations}

    def actualiser(self, valeur_id: int, complet: bool = True, change: bool = True) -> Resultat:
        """Met a jour cours, divisions, fiche et comptes depuis toutes les sources utiles.

        Les cours sont retelecharges en entier : le cours ajuste change retroactivement a
        chaque dividende. Chaque etape a un secours ; une source en panne n'empeche pas les
        autres de passer, elle est simplement signalee dans le message.

        `complet=False` (actualisation quotidienne de toutes les valeurs) : cours et divisions
        seulement, en un appel ; comptes, fiche et calendrier ne bougent qu'une fois par trimestre
        et sont repris une fois par semaine (voir `complet_du`). `change=False` : les taux de
        change ont deja ete charges pour tout le lot."""
        valeur = self._get(valeur_id)
        avertissements: list[str] = []
        nb_cours = 0

        if valeur.source == "yahoo":
            resultat = self._premier_disponible(
                [lambda: _non_vide(yahoo.cours_et_divisions(valeur.symbole)),
                 lambda: _non_vide(yahoo_direct.cours_et_divisions(valeur.symbole))], avertissements)
            if resultat is None:
                raise HTTPException(502, "Cours indisponibles : " + " · ".join(avertissements))
            cours, divisions = resultat
            nb_cours = enregistrer_cours(self._db, valeur.id, cours)
            enregistrer_divisions(self._db, valeur.id, divisions)
            # Valider tout de suite : SQLite n'a qu'un ecrivain a la fois, et les appels reseau
            # qui suivent (comptes : jusqu'a 20 s) bloqueraient les autres valeurs actualisees en parallele.
            self._db.commit()

        if valeur.source == "yahoo" and complet:
            try:
                enregistrer_evenements(self._db, valeur.id, yahoo.evenements(valeur.symbole))
            except Exception as e:        # calendrier secondaire : jamais un echec de toute la valeur
                avertissements.append(f"Calendrier indisponible : {e}")
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

        if change:
            self._actualiser_change(valeur, avertissements)
        nb_fond, sources = self._actualiser_comptes(valeur, avertissements) if complet else (0, [])
        valeur.maj_le = datetime.now(UTC)
        if complet:
            valeur.complet_le = valeur.maj_le
        self._db.commit()
        alertes_service.evaluer(self._db, valeur.id)

        message = f"{valeur.nom} : {nb_cours} séances" + (f", {nb_fond} années de comptes" if complet else "")
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
                self._db.commit()             # meme raison : ne pas garder le verrou pendant la source suivante
                annees |= set(comptes)
                utilisees.append(nom.upper() if nom != "yahoo" else "Yahoo")

        for cle in ("lei", "cik", "devise_comptes"):
            if identite.decouverts.get(cle) and not getattr(valeur, cle):
                setattr(valeur, cle, identite.decouverts[cle])
        return len(annees), utilisees

    def _actualiser_change(self, valeur: Valeur, avertissements: list[str]) -> None:
        """Taux BCE des devises de cotation et de publication des comptes (si autre que l'euro)."""
        for brute in {valeur.devise, valeur.devise_comptes}:
            devise, _ = bce.normaliser(brute)
            if not devise or devise == "EUR":
                continue
            depuis = dernier_taux(self._db, devise)
            try:
                enregistrer_taux(self._db, devise, bce.taux(devise, depuis))
            except SourceIndisponible as e:
                avertissements.append(str(e))

    def actualiser_change(self, devises: set[str | None]) -> list[str]:
        """Taux BCE de plusieurs devises, une fois pour tout un lot de valeurs."""
        avertissements: list[str] = []
        for brute in devises:
            devise, _ = bce.normaliser(brute)
            if devise and devise != "EUR":
                try:
                    enregistrer_taux(self._db, devise, bce.taux(devise, dernier_taux(self._db, devise)))
                except SourceIndisponible as e:
                    avertissements.append(str(e))
        self._db.commit()
        return avertissements

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

    def _get(self, valeur_id: int) -> Valeur:
        valeur = self._db.get(Valeur, valeur_id)
        if not valeur:
            raise HTTPException(404, "Valeur introuvable.")
        return valeur


COMPLET_TOUS_LES = timedelta(days=7)


def complet_du(valeur: Valeur) -> bool:
    """Comptes, fiche et calendrier a reprendre (jamais faits, ou il y a plus d'une semaine)."""
    if valeur.complet_le is None:
        return True
    dernier = valeur.complet_le if valeur.complet_le.tzinfo else valeur.complet_le.replace(tzinfo=UTC)
    return datetime.now(UTC) - dernier > COMPLET_TOUS_LES


def _non_vide(resultat: tuple):
    """(cours, divisions) -> None si aucune seance, pour passer a la source suivante."""
    return resultat if resultat[0] is not None and not resultat[0].empty else None
