"""Actualisation de toutes les valeurs en tache de fond, avec progression.

Une seule actualisation a la fois : relancer pendant une actualisation renvoie simplement
l'etat en cours. Chaque valeur a sa propre session : un echec n'interrompt pas les autres.

Rapidite (plusieurs centaines de valeurs) :
  · PARALLELE valeurs traitees en meme temps (le temps est surtout de l'attente reseau) ;
  · les taux de change sont charges une seule fois pour tout le lot ;
  · actualisation legere (cours et divisions, un seul appel) ; comptes, fiche et calendrier
    seulement s'ils datent de plus d'une semaine (valeur_service.complet_du).
"""
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlmodel import Session, select

from backend.core import reglages
from backend.core.journal import journal
from backend.db.db import engine
from backend.db.schema import Valeur

_log = journal("taches")
PARALLELE = 4          # au-dela, Yahoo limite le debit (erreurs 429)
_verrou = threading.Lock()
_etat: dict = {"en_cours": False, "total": 0, "faits": 0, "courant": None, "echecs": [],
               "avertissements": [], "debut": None, "fin": None}


def etat() -> dict:
    with _verrou:
        return {**_etat, "echecs": list(_etat["echecs"]), "avertissements": list(_etat["avertissements"])}


def lancer() -> dict:
    with _verrou:
        if _etat["en_cours"]:
            return etat_sans_verrou()
        with Session(engine) as db:
            ids = [(v.id, v.nom) for v in db.exec(select(Valeur).order_by(Valeur.nom))]
        _etat.update(en_cours=True, total=len(ids), faits=0, courant=None, echecs=[], avertissements=[],
                     debut=datetime.now(UTC).isoformat(), fin=None)
    threading.Thread(target=_travailler, args=(ids,), daemon=True, name="actualisation").start()
    return etat()


def etat_sans_verrou() -> dict:
    return {**_etat, "echecs": list(_etat["echecs"]), "avertissements": list(_etat["avertissements"])}


def _actualiser_une(valeur_id: int, nom: str) -> None:
    from backend.services.valeur_service import ValeurService, complet_du  # import tardif : evite un cycle
    with _verrou:
        _etat["courant"] = nom
    with Session(engine) as db:
        try:
            valeur = db.get(Valeur, valeur_id)
            if valeur is None:                  # supprimee entre-temps
                return
            resultat = ValeurService(db).actualiser(valeur_id, complet=complet_du(valeur), change=False)
            if resultat.avertissements:
                with _verrou:
                    _etat["avertissements"].append(f"{nom} : {' · '.join(resultat.avertissements)}")
        except HTTPException as e:
            db.rollback()
            _log.warning("actualisation de %s : %s", nom, e.detail)
            with _verrou:
                _etat["echecs"].append(f"{nom} : {e.detail}")
        except Exception as e:     # jamais laisser une valeur bloquer les suivantes
            db.rollback()
            _log.exception("actualisation de %s : erreur inattendue", nom)
            with _verrou:
                _etat["echecs"].append(f"{nom} : {e}")
        finally:
            with _verrou:
                _etat["faits"] += 1


def _travailler(ids: list[tuple[int, str]]) -> None:
    from backend.services.valeur_service import ValeurService
    debut = datetime.now(UTC)
    try:
        with Session(engine) as db:
            devises = {d for v in db.exec(select(Valeur)) for d in (v.devise, v.devise_comptes)}
            avertissements = ValeurService(db).actualiser_change(devises)
        with _verrou:
            _etat["avertissements"] += avertissements
        with ThreadPoolExecutor(max_workers=PARALLELE, thread_name_prefix="actualisation") as groupe:
            list(groupe.map(lambda v: _actualiser_une(*v), ids))
        reglages.ecrire("derniere_actualisation", date.today().isoformat())
        _log.info("actualisation terminee : %d valeur(s), %d echec(s) en %.0f s", len(ids), len(_etat["echecs"]),
                  (datetime.now(UTC) - debut).total_seconds())
    finally:
        with _verrou:
            _etat.update(en_cours=False, courant=None, fin=datetime.now(UTC).isoformat())


def lancer_si_besoin() -> bool:
    """Au demarrage : une actualisation par jour, si le reglage l'autorise."""
    if reglages.lire("actualisation_auto") != "oui":
        return False
    if reglages.lire("derniere_actualisation") == date.today().isoformat():
        return False
    lancer()
    return True
