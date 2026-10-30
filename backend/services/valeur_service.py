from __future__ import annotations

import contextlib
import json
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlmodel import Session, col, select

from backend.db.schema import Transaction, Valeur
from backend.models.valeur import Resultat, ValeurCreate, ValeurRead, ValeurUpdate
from backend.services import alertes_service, cache, consensus_service
from backend.services.stockage import (
    charger_cours,
    charger_divisions,
    clotures_depuis,
    dernier_cours,
    dernier_taux,
    enregistrer_cours,
    enregistrer_dividendes,
    enregistrer_divisions,
    enregistrer_evenements,
    enregistrer_fondamentaux,
    enregistrer_taux,
    journaliser_correction_cours,
)
from backend.sources import bce, catalogue, contre_verification, esef, sec, yahoo, yahoo_direct
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

        dans_catalogue = catalogue.trouver(symbole)
        if dans_catalogue and dans_catalogue[1].source == "bce":
            # Taux europeens : series BCE, en %, sans devise (rien a convertir).
            type_, entree = dans_catalogue
            valeur = Valeur(symbole=symbole, source="bce", nom=data.nom or entree.nom, type=type_, place="BCE",
                            infos=json.dumps({"serie": entree.serie, "detail": entree.detail}))
        elif data.source == "yahoo":
            try:
                fiche = yahoo.fiche(symbole)
                if fiche.type == "crypto" and catalogue.en_dollars(symbole) != symbole:
                    symbole = catalogue.en_dollars(symbole)
                    if self._db.exec(select(Valeur).where(Valeur.symbole == symbole)).first():
                        raise HTTPException(409, f"La valeur « {symbole} » est déjà suivie.")
                    fiche = yahoo.fiche(symbole)
                    dans_catalogue = catalogue.trouver(symbole)
            except SourceIndisponible as e:
                raise HTTPException(502, str(e)) from e
            # Catalogue : nom francais plutot que celui de Yahoo (« Gold Dec 26 », « 10-Year Bond »), et le bon
            # type (Yahoo range les taux americains parmi les indices).
            type_ = dans_catalogue[0] if dans_catalogue else fiche.type
            valeur = Valeur(
                symbole=symbole, source="yahoo", nom=data.nom or catalogue.nom(symbole) or fiche.nom, type=type_,
                devise=None if type_ == "taux" else fiche.devise, place=fiche.place, secteur=fiche.secteur,
                pays=fiche.pays, infos=json.dumps(fiche.infos), isin=(data.isin or "").upper() or None,
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

        if valeur.source in TELECHARGEES and actualiser:
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

    def _cours_recents(self, valeur: Valeur, avertissements: list[str]) -> int | None:
        """Seances manquantes seulement (+ 10 jours de recouvrement). None s'il faut tout recharger :
        pas encore de cours, dividende ou division dans la periode (le cours ajuste de tout le passe
        change), ou cours de recouvrement differents de ceux deja enregistres (source corrigee)."""
        dernier = dernier_cours(self._db, valeur.id)
        if dernier is None:
            return None
        debut = dernier - timedelta(days=RECOUVREMENT_JOURS)
        resultat = self._premier_disponible(
            [lambda: _non_vide(yahoo.cours_recents(valeur.symbole, debut)),
             lambda: _non_vide(yahoo_direct.cours_recents(valeur.symbole, debut))], avertissements)
        if resultat is None:
            return None
        cours, evenement = resultat
        if evenement:
            return None
        connues = clotures_depuis(self._db, valeur.id, debut)
        for jour, cloture in zip(cours["jour"], cours["cloture"], strict=True):
            # Le dernier jour connu a pu etre enregistre en cours de seance : son ecart ne prouve rien.
            if jour < dernier and connues.get(jour) and abs(cloture / connues[jour] - 1) > ECART_RECOUVREMENT:
                return None
        nouvelles = sum(1 for j in cours["jour"] if j > dernier)
        enregistrer_cours(self._db, valeur.id, cours)
        return nouvelles

    def actualiser(self, valeur_id: int, complet: bool = True, change: bool = True, recents: bool = False) -> Resultat:
        """Met a jour cours, divisions, fiche et comptes depuis toutes les sources utiles.

        Les cours sont retelecharges en entier : le cours ajuste change retroactivement a
        chaque dividende. Chaque etape a un secours ; une source en panne n'empeche pas les
        autres de passer, elle est simplement signalee dans le message.

        `recents=True` (bouton « Actualiser les cours ») : seulement les seances depuis la derniere
        mise a jour, si rien n'oblige a recharger tout l'historique (voir _cours_recents).

        `complet=False` (actualisation quotidienne de toutes les valeurs) : cours et divisions
        seulement, en un appel ; comptes, fiche et calendrier ne bougent qu'une fois par trimestre
        et sont repris une fois par semaine (voir `complet_du`). `change=False` : les taux de
        change ont deja ete charges pour tout le lot."""
        valeur = self._get(valeur_id)
        avertissements: list[str] = []
        nb_cours = 0

        nouvelles = self._cours_recents(valeur, avertissements) if valeur.source == "yahoo" and recents else None
        if nouvelles is not None:
            self._db.commit()
        elif valeur.source == "yahoo":
            resultat = self._premier_disponible(
                [lambda: _non_vide(yahoo.cours_et_divisions(valeur.symbole)),
                 lambda: _non_vide(yahoo_direct.cours_et_divisions(valeur.symbole))], avertissements)
            if resultat is None:
                raise HTTPException(502, "Cours indisponibles : " + " · ".join(avertissements))
            cours, divisions = resultat
            # Journal des corrections : la source a-t-elle retouche des seances deja connues ? (Une
            # nouvelle division modifie legitimement tout le passe : pas une correction.)
            if set(divisions) == set(charger_divisions(self._db, valeur.id)):
                journaliser_correction_cours(self._db, valeur.id, cours, clotures_depuis(self._db, valeur.id, date.min))
            nb_cours = enregistrer_cours(self._db, valeur.id, cours)
            enregistrer_divisions(self._db, valeur.id, divisions)
            enregistrer_dividendes(self._db, valeur.id, cours)
            # Valider tout de suite : SQLite n'a qu'un ecrivain a la fois, et les appels reseau
            # qui suivent (comptes : jusqu'a 20 s) bloqueraient les autres valeurs actualisees en parallele.
            self._db.commit()
        elif valeur.source == "bce":
            nb_cours = self._cours_bce(valeur, avertissements, recents)

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
            if valeur.type == "taux":
                valeur.devise = None          # Yahoo donne « USD » pour un taux americain : c'est un %
            if valeur.type == "action":
                # Historique des previsions : un instantane par actualisation complete (secondaire : sans erreur).
                with contextlib.suppress(SourceIndisponible):
                    consensus_service.enregistrer(self._db, valeur_id, yahoo.consensus(valeur.symbole))
        self._db.flush()

        if valeur.source == "yahoo" and complet and contre_verification.couvre(valeur.symbole, valeur.place, valeur.type):
            try:
                self._contre_verifier(valeur, avertissements)
            except Exception as e:        # controle secondaire : jamais un echec de toute la valeur
                avertissements.append(f"Contre-vérification des cours impossible : {e}")
        if change:
            self._actualiser_change(valeur, avertissements)
        nb_fond, sources = self._actualiser_comptes(valeur, avertissements) if complet else (0, [])
        valeur.maj_le = datetime.now(UTC)
        if complet:
            valeur.complet_le = valeur.maj_le
        self._db.commit()
        alertes_service.evaluer(self._db, valeur.id)

        message = (f"{valeur.nom} : {nouvelles} nouvelle(s) séance(s)" if nouvelles is not None
                   else f"{valeur.nom} : {nb_cours} séances") + (f", {nb_fond} années de comptes" if complet else "")
        message += f" ({', '.join(sources)})." if sources else "."
        if avertissements:
            message += " " + " · ".join(avertissements)
        return Resultat(message=message, cours=nb_cours, fondamentaux=nb_fond, avertissements=avertissements)

    def _contre_verifier(self, valeur: Valeur, avertissements: list[str]) -> None:
        """Compare les clotures des 2 dernieres annees a Euronext ou Nasdaq (une fois par semaine, avec la mise a
        jour complete). Resultat garde dans `infos` ; au passage, l'ISIN d'une valeur Euronext est complete."""
        try:
            if "." in valeur.symbole:
                trouve = contre_verification.isin_euronext(valeur.symbole)
                if not trouve:
                    return
                isin, mic = trouve
                valeur.isin = valeur.isin or isin
                autre, source = contre_verification.euronext(isin, mic), "Euronext"
            else:
                autre, source = contre_verification.nasdaq(valeur.symbole), "Nasdaq"
        except SourceIndisponible as e:
            avertissements.append(f"Contre-vérification des cours impossible : {e}")
            return
        if autre.empty:
            return
        cloture = charger_cours(self._db, valeur.id)["cloture"]
        resultat = contre_verification.comparer(cloture[cloture.index >= autre.index[0]], autre, source)
        valeur.infos = json.dumps(json.loads(valeur.infos or "{}") | {"contre_verification": resultat})
        if resultat["statut"] == "alerte":
            avertissements.append(f"Cours différents de {source} sur {resultat['desaccords']} séances "
                                  f"(jusqu'à {resultat['ecart_max']:+.1%} le {resultat['jour_ecart_max']})")

    def _cours_bce(self, valeur: Valeur, avertissements: list[str], recents: bool) -> int:
        """Taux europeens (BCE) : la serie entiere est petite ; en mode « cours », le dernier mois seulement."""
        trouve = catalogue.trouver(valeur.symbole)        # le catalogue d'abord : valeur recue par un partage
        cle = trouve[1].serie if trouve else json.loads(valeur.infos or "{}").get("serie")
        if not cle:
            raise HTTPException(409, f"{valeur.nom} : série BCE inconnue.")
        dernier = dernier_cours(self._db, valeur.id)
        debut = dernier - timedelta(days=40) if recents and dernier else None
        try:
            cours = bce.serie(cle, debut)
        except SourceIndisponible as e:
            if dernier is None:
                raise HTTPException(502, str(e)) from e
            avertissements.append(str(e))
            return 0
        nombre = enregistrer_cours(self._db, valeur.id, cours) if not cours.empty else 0
        self._db.commit()
        return nombre

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


TELECHARGEES = ("yahoo", "bce")    # sources actualisees automatiquement (« import » : fichiers a la main)
COMPLET_TOUS_LES = timedelta(days=7)
RECOUVREMENT_JOURS = 10          # seances deja connues retelechargees pour verifier qu'elles n'ont pas change
ECART_RECOUVREMENT = 0.005      # au-dela, la source a corrige son historique : on recharge tout


def complet_du(valeur: Valeur) -> bool:
    """Comptes, fiche et calendrier a reprendre (jamais faits, ou il y a plus d'une semaine)."""
    if valeur.complet_le is None:
        return True
    dernier = valeur.complet_le if valeur.complet_le.tzinfo else valeur.complet_le.replace(tzinfo=UTC)
    return datetime.now(UTC) - dernier > COMPLET_TOUS_LES


def _non_vide(resultat: tuple):
    """(cours, divisions) -> None si aucune seance, pour passer a la source suivante."""
    return resultat if resultat[0] is not None and not resultat[0].empty else None
