"""Suivi au quotidien : alertes, calendrier, actualites et resume du jour."""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.core import reglages
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
    lignes = db.exec(select(Evenement, Valeur).join(Valeur, Valeur.id == Evenement.valeur_id)
                     .where(Evenement.jour >= debut, Evenement.jour <= fin).order_by(Evenement.jour))
    return [{"jour": e.jour.isoformat(), "type": e.type, "detail": e.detail, "valeur_id": v.id, "nom": v.nom,
             "symbole": v.symbole} for e, v in lignes]


@router.get("/valeurs/{valeur_id}/actualites")
def actualites(valeur_id: int, db: Session = Depends(get_session)):
    valeur = db.get(Valeur, valeur_id)
    if not valeur:
        raise HTTPException(404, "Valeur introuvable.")
    return source_actualites.actualites(valeur.nom, valeur.symbole)


@router.get("/resume")
def resume(db: Session = Depends(get_session)):
    """Ce qui compte aujourd'hui, en un coup d'oeil."""
    # Donnees suspectes (contrôle qualite) : exclues des palmares, elles fausseraient tout.
    lignes = [l for l in AnalyseService(db).synthese()
              if l.get("variation_jour") is not None and l.get("qualite") != "alerte"]
    tri = sorted(lignes, key=lambda l: l["variation_jour"])
    porte = PortefeuilleService(db).synthese()
    a_venir = calendrier(jours_avant=0, jours_apres=14, db=db)

    def court(l):
        return {"id": l["valeur"]["id"], "nom": l["valeur"]["nom"], "variation_jour": l.get("variation_jour"),
                "position": l.get("position"), "zone": l.get("zone"), "dernier": l.get("dernier"),
                "devise": "pts" if l["valeur"].get("type") == "indice" else l["valeur"].get("devise")}
    return {
        "derniere_actualisation": reglages.lire("derniere_actualisation") or None,
        "portefeuille": None if porte.get("vide") else {
            "valeur": porte["totaux"]["valeur"], "variation_jour": porte["totaux"]["variation_jour"],
            "plus_value_latente": porte["totaux"]["plus_value_latente"], "twr": porte["performance"].get("twr"),
        },
        "alertes": AlerteService(db).declenchements(limite=10),
        "hausses": [court(l) for l in reversed(tri[-3:]) if l["variation_jour"] > 0],
        "baisses": [court(l) for l in tri[:3] if l["variation_jour"] < 0],
        "opportunites": [court(l) for l in lignes if l.get("zone") in ("opportunite_manifeste", "sous_evalue")],
        "cheres": [court(l) for l in lignes if l.get("zone") == "surevaluation_manifeste"],
        "evenements": a_venir,
        "nombre_valeurs": len(lignes),
    }
