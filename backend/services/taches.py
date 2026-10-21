"""Actualisation de toutes les valeurs en tache de fond, avec progression.

Un seul fil d'execution a la fois : relancer pendant une actualisation renvoie simplement
l'etat en cours. Chaque valeur a sa propre session : un echec n'interrompt pas les autres.
"""
import threading
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlmodel import Session, select

from backend.core import reglages
from backend.core.journal import journal
from backend.db.db import engine
from backend.db.schema import Valeur

_log = journal("taches")
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


def _travailler(ids: list[tuple[int, str]]) -> None:
    from backend.services.valeur_service import ValeurService  # import tardif : evite un cycle
    try:
        for valeur_id, nom in ids:
            with _verrou:
                _etat["courant"] = nom
            with Session(engine) as db:
                try:
                    resultat = ValeurService(db).actualiser(valeur_id)
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
            with _verrou:
                _etat["faits"] += 1
        reglages.ecrire("derniere_actualisation", date.today().isoformat())
        _log.info("actualisation terminee : %d valeur(s), %d echec(s)", len(ids), len(_etat["echecs"]))
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
