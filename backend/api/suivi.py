"""Suivi au quotidien : alertes, calendrier, actualites et resume du jour."""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, col, func, select

from backend.db.db import get_session
from backend.db.schema import Evenement, Valeur
from backend.services.alertes_service import TYPES, AlerteService, notifier
from backend.services.analyse_service import AnalyseService
from backend.services.portefeuille_service import PortefeuilleService
from backend.sources import actualites as source_actualites

router = APIRouter(tags=["Suivi"])


class AlerteEcriture(BaseModel):
    valeur_id: int
    type: str
    seuil: Optional[float] = None
    active: bool = True


@router.get("/alertes")
def alertes(valeur_id: Optional[int] = None, db: Session = Depends(get_session)):
    return {"types": {k: {"libelle": v[0], "unite": v[1]} for k, v in TYPES.items()},
            "alertes": AlerteService(db).alertes(valeur_id)}


@router.post("/alertes", status_code=201)
def creer_alerte(data: AlerteEcriture, db: Session = Depends(get_session)):
    return AlerteService(db).ecrire(data.valeur_id, data.type, data.seuil, data.active)


@router.put("/alertes/{alerte_id}")
def modifier_alerte(alerte_id: int, data: AlerteEcriture, db: Session = Depends(get_session)):
    return AlerteService(db).ecrire(data.valeur_id, data.type, data.seuil, data.active, alerte_id)


@router.delete("/alertes/{alerte_id}", status_code=204)
def supprimer_alerte(alerte_id: int, db: Session = Depends(get_session)):
    AlerteService(db).supprimer(alerte_id)


@router.get("/alertes/declenchements")
def declenchements(db: Session = Depends(get_session)):
    return AlerteService(db).declenchements()


@router.post("/alertes/lues", status_code=204)
def marquer_lues(db: Session = Depends(get_session)):
    AlerteService(db).marquer_lus()


@router.post("/alertes/essai")
def essai_notification():
    """Envoie une notification d'essai sur les canaux configures."""
    canaux = notifier(["Ceci est une notification d'essai : les alertes vous parviendront ainsi."])
    return {"canaux": canaux}


@router.get("/calendrier")
def calendrier(jours_avant: int = 30, jours_apres: int = 90, db: Session = Depends(get_session)):
    debut, fin = date.today() - timedelta(days=jours_avant), date.today() + timedelta(days=jours_apres)
    lignes = db.exec(select(Evenement, Valeur).join(Valeur, col(Valeur.id) == col(Evenement.valeur_id))
                     .where(Evenement.jour >= debut, Evenement.jour <= fin).order_by(col(Evenement.jour)))
    return [_evenement(e, v) for e, v in lignes]


def _evenement(e: Evenement, v: Valeur) -> dict:
    return {"jour": e.jour.isoformat(), "type": e.type, "detail": e.detail, "valeur_id": v.id, "nom": v.nom,
            "symbole": v.symbole}


@router.get("/valeurs/{valeur_id}/actualites")
def actualites(valeur_id: int, db: Session = Depends(get_session)):
    valeur = db.get(Valeur, valeur_id)
    if not valeur:
        raise HTTPException(404, "Valeur introuvable.")
    return source_actualites.actualites(valeur.nom, valeur.symbole)


@router.get("/resume")
def resume(db: Session = Depends(get_session)):
    """Ce qui compte aujourd'hui, en un coup d'oeil : les actions seulement, le reste se suit ailleurs.
    Le portefeuille reste entier : c'est ce que vous possedez."""
    toutes = AnalyseService(db).synthese()
    actions = [l for l in toutes if l["valeur"]["type"] == "action"]
    # Donnees suspectes (contrôle qualite) : exclues des palmares, elles fausseraient tout.
    lignes = [l for l in actions if l.get("variation_jour") is not None and l.get("qualite") != "alerte"]
    tri = sorted(lignes, key=lambda l: l["variation_jour"])
    positions = sorted((l for l in lignes if l.get("position") is not None), key=lambda l: l["position"])
    porte = PortefeuilleService(db).synthese()
    aujourdhui = date.today()
    a_venir = select(Evenement, Valeur).join(Valeur, col(Valeur.id) == col(Evenement.valeur_id)) \
        .where(Valeur.type == "action", Evenement.jour >= aujourdhui)
    prochains = db.exec(a_venir.order_by(col(Evenement.jour)).limit(10))
    sous_14_jours = db.exec(select(func.count()).select_from(Evenement).join(Valeur, col(Valeur.id) == col(Evenement.valeur_id))
                            .where(Valeur.type == "action", Evenement.jour >= aujourdhui,
                                   Evenement.jour <= aujourdhui + timedelta(days=14))).one()

    def court(l):
        return {"id": l["valeur"]["id"], "nom": l["valeur"]["nom"], "variation_jour": l.get("variation_jour"),
                "position": l.get("position"), "zone": l.get("zone"), "dernier": l.get("dernier"),
                "devise": "pts" if l["valeur"].get("type") == "indice" else l["valeur"].get("devise")}
    return {
        "derniere_actualisation": max((m for l in toutes if (m := l["valeur"].get("maj_le"))), default=None),
        "portefeuille": None if porte.get("vide") else {
            "valeur": porte["totaux"]["valeur"], "variation_jour": porte["totaux"]["variation_jour"],
            "plus_value_latente": porte["totaux"]["plus_value_latente"], "twr": porte["performance"].get("twr"),
        },
        "alertes": AlerteService(db).declenchements(limite=5, type_valeur="action"),
        "hausses": [court(l) for l in reversed(tri[-5:]) if l["variation_jour"] > 0],
        "baisses": [court(l) for l in tri[:5] if l["variation_jour"] < 0],
        "sous_droite": [court(l) for l in positions[:5] if l["position"] < 0],
        "dessus_droite": [court(l) for l in reversed(positions[-5:]) if l["position"] > 0],
        "evenements": [_evenement(e, v) for e, v in prochains],
        "evenements_14_jours": sous_14_jours,
        "nombre_actions": len(actions),
    }
