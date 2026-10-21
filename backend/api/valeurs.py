import time
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session

from backend.analyse.valorisation import Hypotheses
from backend.db.db import get_session
from backend.db.schema import Valeur
from backend.models.valeur import Resultat, ValeurCreate, ValeurRead, ValeurUpdate
from backend.services import export_service, taches, technique_service
from backend.services.analyse_service import AnalyseService
from backend.services.valeur_service import ValeurService
from backend.sources import yahoo
from backend.sources.base import SourceIndisponible

router = APIRouter(tags=["Valeurs"], prefix="/valeurs")
_CONSENSUS: dict[str, tuple[float, dict]] = {}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def get_service(session: Session = Depends(get_session)) -> ValeurService:
    return ValeurService(session=session)


def get_analyse(session: Session = Depends(get_session)) -> AnalyseService:
    return AnalyseService(session=session)


@router.get("/recherche")
def rechercher(q: str = Query(min_length=1)):
    """Recherche d'un symbole chez Yahoo (« air liquide », « AAPL », « CAC 40 »…)."""
    try:
        return yahoo.rechercher(q)
    except yahoo.SourceIndisponible as e:
        raise HTTPException(502, str(e)) from e


@router.get("", response_model=list[ValeurRead])
def list_valeurs(service: ValeurService = Depends(get_service)):
    return service.list()


@router.get("/synthese")
def synthese(analyse: AnalyseService = Depends(get_analyse)):
    return analyse.synthese()


@router.post("", response_model=ValeurRead, status_code=201)
def create_valeur(data: ValeurCreate, service: ValeurService = Depends(get_service)):
    return service.create(data)


@router.post("/actualiser")
def actualiser_tout():
    """Lance l'actualisation de toutes les valeurs en tache de fond ; renvoie la progression."""
    return taches.lancer()


@router.get("/actualisation")
def progression():
    return taches.etat()


@router.get("/{valeur_id}", response_model=ValeurRead)
def get_valeur(valeur_id: int, service: ValeurService = Depends(get_service)):
    return service.get(valeur_id)


@router.get("/{valeur_id}/analyse")
def analyse_valeur(
    valeur_id: int,
    dividendes: bool = True,
    debut: Optional[date] = None,
    en_euros: bool = False,
    analyse: AnalyseService = Depends(get_analyse),
):
    return analyse.analyse(valeur_id, dividendes, debut, en_euros)


@router.get("/{valeur_id}/technique")
def technique(
    valeur_id: int,
    unite: str = "jour",
    mm: str = Query("20,50,200", pattern=r"^\d{1,3}(,\d{1,3}){0,5}$"),
    rsi: int = Query(14, ge=2, le=100), bollinger: int = Query(20, ge=5, le=100),
    stochastique: int = Query(14, ge=3, le=100), atr: int = Query(14, ge=2, le=100), adx: int = Query(14, ge=2, le=100),
    session: Session = Depends(get_session),
):
    """Analyse technique : unite de temps (jour, semaine, mois) et periodes au choix."""
    periodes = [int(n) for n in mm.split(",") if 0 < int(n) <= 400]
    return technique_service.technique(session, valeur_id, unite, periodes, rsi, bollinger, stochastique, atr, adx)


@router.get("/{valeur_id}/consensus")
def consensus(valeur_id: int, session: Session = Depends(get_session)):
    """Previsions des analystes (Yahoo), gardees 12 h en memoire : elles bougent peu dans la journee."""
    valeur = session.get(Valeur, valeur_id)
    if not valeur:
        raise HTTPException(404, "Valeur introuvable.")
    if valeur.type == "indice" or valeur.source != "yahoo":
        return {"indisponible": "Pas de prévisions d'analystes pour ce type de valeur."}
    en_cache = _CONSENSUS.get(valeur.symbole)
    if en_cache and time.monotonic() - en_cache[0] < 12 * 3600:
        return en_cache[1]
    try:
        donnees = yahoo.consensus(valeur.symbole)
    except SourceIndisponible as e:
        return {"indisponible": str(e)}
    resultat = donnees or {"indisponible": "Aucun analyste ne suit cette valeur chez Yahoo."}
    _CONSENSUS[valeur.symbole] = (time.monotonic(), resultat)
    return resultat


@router.get("/{valeur_id}/export.xlsx")
def exporter(valeur_id: int, session: Session = Depends(get_session)):
    """Classeur Excel : resume, cours mensuels, comptes, ratios, multiples."""
    if not session.get(Valeur, valeur_id):
        raise HTTPException(404, "Valeur introuvable.")
    nom, contenu = export_service.valeur(session, valeur_id)
    return Response(contenu, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{nom}.xlsx"'})


@router.get("/{valeur_id}/valorisation")
def valorisation(
    valeur_id: int,
    croissance: float = Query(0.06, ge=-0.2, le=0.5),
    annees: int = Query(10, ge=1, le=30),
    terminale: float = Query(0.02, ge=-0.02, le=0.05),
    actualisation: float = Query(0.08, ge=0.02, le=0.3),
    base_fcf: Optional[float] = None,
    analyse: AnalyseService = Depends(get_analyse),
):
    """Modeles de valeur intrinseque avec des hypotheses choisies."""
    return analyse.valorisation(valeur_id, Hypotheses(croissance, annees, terminale, actualisation, base_fcf))


@router.get("/{valeur_id}/secteur")
def secteur(valeur_id: int, analyse: AnalyseService = Depends(get_analyse)):
    """Multiples des valeurs suivies du meme secteur."""
    return analyse.secteur(valeur_id)


@router.patch("/{valeur_id}", response_model=ValeurRead)
def update_valeur(valeur_id: int, data: ValeurUpdate, service: ValeurService = Depends(get_service)):
    return service.update(valeur_id, data)


@router.post("/{valeur_id}/actualiser", response_model=Resultat)
def actualiser(valeur_id: int, service: ValeurService = Depends(get_service)):
    return service.actualiser(valeur_id)


@router.delete("/{valeur_id}", status_code=204)
def delete_valeur(valeur_id: int, service: ValeurService = Depends(get_service)):
    service.delete(valeur_id)
