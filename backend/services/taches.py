"""Actualisation de toutes les valeurs en tache de fond, avec progression.

Une seule actualisation a la fois : relancer pendant une actualisation renvoie simplement
l'etat en cours. Chaque valeur a sa propre session : un echec n'interrompt pas les autres.

Rapidite (plusieurs centaines de valeurs) :
  · PARALLELE valeurs traitees en meme temps (le temps est surtout de l'attente reseau) ;
  · les taux de change sont charges une seule fois pour tout le lot ;
  · actualisation legere (cours et divisions, un seul appel) ; comptes, fiche et calendrier
    seulement s'ils datent de plus d'une semaine (valeur_service.complet_du).
"""
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlmodel import Session, select

from backend.core import brut, reglages
from backend.core.journal import journal
from backend.db.db import engine
from backend.db.schema import Valeur
from backend.services import cache

_log = journal("taches")
PARALLELE = 4          # au-dela, Yahoo limite le debit (erreurs 429)
_verrou = threading.Lock()
_etat: dict = {"en_cours": False, "total": 0, "faits": 0, "courant": None, "echecs": [],
               "avertissements": [], "debut": None, "fin": None}


def etat() -> dict:
    with _verrou:
        return {**_etat, "echecs": list(_etat["echecs"]), "avertissements": list(_etat["avertissements"])}


MODES = ("auto", "cours", "complet")


def lancer(mode: str = "auto") -> dict:
    """`cours` : seances recentes seulement (rapide) ; `complet` : tout, pour toutes les valeurs ;
    `auto` (demarrage, imports) : seances recentes, et le complet hebdomadaire quand il est du."""
    with _verrou:
        if _etat["en_cours"]:
            return etat_sans_verrou()
        with Session(engine) as db:
            ids = [(v.id, v.nom) for v in db.exec(select(Valeur).order_by(Valeur.nom))]
        _etat.update(en_cours=True, total=len(ids), faits=0, courant=None, echecs=[], avertissements=[],
                     debut=datetime.now(UTC).isoformat(), fin=None, mode=mode)
    threading.Thread(target=_travailler, args=(ids, mode), daemon=True, name="actualisation").start()
    return etat()


def etat_sans_verrou() -> dict:
    return {**_etat, "echecs": list(_etat["echecs"]), "avertissements": list(_etat["avertissements"])}


ABANDON = 5             # echecs d'affilee apres lesquels l'actualisation rapide ne reessaie plus la valeur
# secondes avant le second essai des valeurs en echec (coupure, limite de debit) ; 0 dans les tests
REPRISE_APRES = float(os.environ.get("BOURSE_REPRISE_APRES", "20"))


def _actualiser_une(valeur_id: int, nom: str, mode: str = "auto", dernier_essai: bool = True) -> bool:
    """Vrai si la valeur est actualisee (ou volontairement ignoree). `dernier_essai=False` : un echec n'est
    ni compte ni signale, la valeur sera reessayee en fin de lot."""
    from backend.services.valeur_service import ValeurService, complet_du  # import tardif : evite un cycle
    with _verrou:
        _etat["courant"] = nom
    erreur = None
    with Session(engine) as db:
        try:
            valeur = db.get(Valeur, valeur_id)
            if valeur is None:                  # supprimee entre-temps
                return True
            if valeur.echecs >= ABANDON and mode != "complet":
                # Valeur « morte » (retiree de la cote, symbole change) : plus d'appels inutiles a chaque
                # actualisation rapide ; « Tout mettre a jour » la reessaie.
                with _verrou:
                    _etat["avertissements"].append(f"{nom} : ignorée après {valeur.echecs} échecs d'affilée "
                                                   "(cotation arrêtée ou symbole changé ?) ; « Tout mettre à jour » la réessaie")
                return True
            complet = mode == "complet" or (mode == "auto" and complet_du(valeur))
            # Un historique complet est retelecharge quand tout est mis a jour ; sinon, seances recentes.
            resultat = ValeurService(db).actualiser(valeur_id, complet=complet, change=False, recents=mode != "complet")
            if valeur.echecs:
                valeur.echecs, valeur.derniere_erreur = 0, None
                db.commit()
            if resultat.avertissements:
                with _verrou:
                    _etat["avertissements"].append(f"{nom} : {' · '.join(resultat.avertissements)}")
            return True
        except HTTPException as e:
            db.rollback()
            _log.warning("actualisation de %s : %s", nom, e.detail)
            erreur = str(e.detail)
        except Exception as e:     # jamais laisser une valeur bloquer les suivantes
            db.rollback()
            _log.exception("actualisation de %s : erreur inattendue", nom)
            erreur = str(e)
        finally:
            if erreur is None or dernier_essai:
                with _verrou:
                    _etat["faits"] += 1
    if dernier_essai:
        with Session(engine) as db:
            valeur = db.get(Valeur, valeur_id)
            if valeur is not None:
                valeur.echecs += 1
                valeur.derniere_erreur = erreur[:500]
                db.commit()
                cache.invalider(valeur_id)
        with _verrou:
            _etat["echecs"].append(f"{nom} : {erreur}")
    return False


def _travailler(ids: list[tuple[int, str]], mode: str = "auto") -> None:
    from backend.services import taux_service
    from backend.services.valeur_service import ValeurService
    debut = datetime.now(UTC)
    try:
        with Session(engine) as db:
            valeurs = list(db.exec(select(Valeur)))
            devises = {d for v in valeurs for d in (v.devise, v.devise_comptes)}
            avertissements = ValeurService(db).actualiser_change(devises)
            if any(v.type == "action" for v in valeurs):         # taux sans risque : pour le DCF des actions
                avertissements = [*avertissements, *taux_service.actualiser(db)]
        with _verrou:
            _etat["avertissements"] += avertissements
        with ThreadPoolExecutor(max_workers=PARALLELE, thread_name_prefix="actualisation") as groupe:
            reussites = list(groupe.map(lambda v: _actualiser_une(v[0], v[1], mode, dernier_essai=False), ids))
        # Reprise automatique : les echecs passagers (coupure, limite de debit) passent souvent au second essai,
        # une valeur a la fois apres une pause.
        a_reprendre = [v for v, ok in zip(ids, reussites, strict=True) if not ok]
        if a_reprendre:
            _log.info("reprise de %d valeur(s) en echec", len(a_reprendre))
            time.sleep(REPRISE_APRES)
            for v in a_reprendre:
                _actualiser_une(v[0], v[1], mode)
        reglages.ecrire("derniere_actualisation", date.today().isoformat())
        brut.purger()
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
