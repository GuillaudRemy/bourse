"""Chercher : screener (filtres enregistres) et comparaison de valeurs."""
import json
from datetime import date
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from backend.analyse.backtest import Regle, agreger, simuler
from backend.analyse.frais import assujetti_ttf, ordre, taux_ttf
from backend.core import reglages
from backend.db.db import get_session
from backend.db.schema import Filtre, ListeValeur, Valeur
from backend.services.analyse_service import AnalyseService
from backend.services.stockage import charger_cours
from backend.sources import catalogue

router = APIRouter(tags=["Screener et comparaison"])


@router.get("/screener")
def screener(liste_id: Optional[int] = None, db: Session = Depends(get_session)):
    """Une ligne par valeur, avec tous les criteres filtrables (fiches resumees en cache)."""
    requete = select(Valeur).order_by(Valeur.nom)
    if liste_id:
        ids = [lv.valeur_id for lv in db.exec(select(ListeValeur).where(ListeValeur.liste_id == liste_id))]
        requete = requete.where(col(Valeur.id).in_(ids))
    service = AnalyseService(db)
    return [service.fiche_resumee(v) for v in db.exec(requete)]


class FiltreEcriture(BaseModel):
    nom: str = Field(min_length=1, max_length=60)
    criteres: dict


@router.get("/filtres")
def filtres(db: Session = Depends(get_session)):
    return [{"id": f.id, "nom": f.nom, "criteres": json.loads(f.criteres)} for f in db.exec(select(Filtre).order_by(Filtre.nom))]


@router.put("/filtres")
def enregistrer_filtre(data: FiltreEcriture, db: Session = Depends(get_session)):
    """Cree ou remplace le filtre de ce nom."""
    filtre = db.exec(select(Filtre).where(Filtre.nom == data.nom.strip())).first() or Filtre(nom=data.nom.strip())
    filtre.criteres = json.dumps(data.criteres, ensure_ascii=False)
    db.add(filtre)
    db.commit()
    return {"id": filtre.id, "nom": filtre.nom, "criteres": data.criteres}


@router.delete("/filtres/{filtre_id}", status_code=204)
def supprimer_filtre(filtre_id: int, db: Session = Depends(get_session)):
    filtre = db.get(Filtre, filtre_id)
    if not filtre:
        raise HTTPException(404, "Filtre introuvable.")
    db.delete(filtre)
    db.commit()


@router.get("/comparer")
def comparer(ids: str = Query(min_length=1), annees: int = Query(10, ge=1, le=40), reference: Optional[int] = None,
             db: Session = Depends(get_session)):
    """Cours hebdomadaires en base 100 (dividendes reinvestis quand disponibles) sur la periode
    commune, la force relative de chacun face a la reference, et leurs fiches resumees."""
    try:
        identifiants = [int(i) for i in ids.split(",") if i.strip()][:8]
    except ValueError as e:
        raise HTTPException(422, "Identifiants invalides.") from e
    if reference and reference not in identifiants:
        identifiants.append(reference)
    service, series, fiches = AnalyseService(db), {}, {}
    for vid in identifiants:
        valeur = db.get(Valeur, vid)
        if not valeur:
            continue
        cours = charger_cours(db, vid)
        if cours.empty:
            continue
        base = cours["ajuste"] if cours["ajuste"].notna().mean() > 0.9 else cours["cloture"]
        series[vid] = base.dropna().resample("W").last()
        fiches[vid] = service.fiche_resumee(valeur)
    if not series:
        raise HTTPException(404, "Aucune des valeurs n'a de cours.")
    df = pd.DataFrame(series).dropna()
    df = df[df.index >= df.index.max() - pd.DateOffset(years=annees)]
    if df.empty:
        raise HTTPException(409, "Pas de période commune à ces valeurs.")
    base100 = df / df.iloc[0] * 100
    resultat = {
        "jours": [j.strftime("%Y-%m-%d") for j in base100.index],
        "series": {str(vid): [round(float(v), 3) for v in base100[vid]] for vid in base100.columns},
        "fiches": {str(k): v for k, v in fiches.items()},
        "debut": base100.index[0].strftime("%Y-%m-%d"),
    }
    if reference and reference in base100.columns:
        resultat["force_relative"] = {
            str(vid): [round(float(v), 3) for v in base100[vid] / base100[reference] * 100]
            for vid in base100.columns if vid != reference}
        resultat["reference"] = reference
    return resultat


def _regle(achat: float, vente: float, frais: Optional[float], annees_min: int, fenetre: Optional[int], liquidites: float,
           depart_investi: bool, valeur: Optional[Valeur] = None) -> Regle:
    """`frais` vide : courtage par defaut des reglages (ramene a un ordre type) + TTF a l'achat si due."""
    if achat >= vente:
        raise HTTPException(422, "Le seuil d'achat doit être inférieur au seuil de vente.")
    frais_vente = None
    if frais is None:
        montant = reglages.nombre("montant_ordre", 2000.0) or 2000.0
        courtage = ordre(montant, "vente", date.today(), reglages.grille_frais(), False)["courtage"] / montant
        infos = json.loads(valeur.infos) if valeur and valeur.infos else {}
        ttf = taux_ttf(date.today()) if valeur and assujetti_ttf(valeur.type, valeur.pays, infos.get("capitalisation")) else 0.0
        frais, frais_vente = courtage + ttf, courtage
    return Regle(achat, vente, frais, annees_min, fenetre, liquidites, depart_investi, frais_vente)


def _cours_base(db: Session, valeur_id: int) -> pd.Series:
    cours = charger_cours(db, valeur_id)
    if cours.empty:
        return pd.Series(dtype=float)
    return (cours["ajuste"] if cours["ajuste"].notna().mean() > 0.9 else cours["cloture"]).dropna()


@router.get("/backtest/{valeur_id}")
def backtest_valeur(valeur_id: int, achat: float = -1.0, vente: float = 1.0, frais: Optional[float] = Query(None, ge=0, le=0.05),
                    annees_min: int = Query(10, ge=3, le=30), fenetre: Optional[int] = Query(None, ge=5, le=40),
                    liquidites: float = Query(0.0, ge=0, le=0.1), depart_investi: bool = False,
                    db: Session = Depends(get_session)):
    valeur = db.get(Valeur, valeur_id)
    if not valeur:
        raise HTTPException(404, "Valeur introuvable.")
    if valeur.type in catalogue.SANS_DROITE:
        raise HTTPException(409, "Pas de droite de régression pour une devise ou un taux : rien à simuler.")
    regle = _regle(achat, vente, frais, annees_min, fenetre, liquidites, depart_investi, valeur)
    resultat = simuler(_cours_base(db, valeur_id), regle)
    if resultat is None:
        raise HTTPException(409, f"Historique trop court : il faut au moins {annees_min} ans, plus un an de simulation.")
    return resultat | {"frais_achat": regle.frais, "frais_vente": regle.frais if regle.frais_vente is None else regle.frais_vente}


@router.get("/backtest")
def backtest_univers(liste_id: Optional[int] = None, achat: float = -1.0, vente: float = 1.0,
                     frais: Optional[float] = Query(None, ge=0, le=0.05), annees_min: int = Query(10, ge=3, le=30),
                     fenetre: Optional[int] = Query(None, ge=5, le=40), liquidites: float = Query(0.0, ge=0, le=0.1),
                     depart_investi: bool = False, db: Session = Depends(get_session)):
    """La meme regle appliquee a chaque action suivie (ou d'une liste)."""
    _regle(achat, vente, frais, annees_min, fenetre, liquidites, depart_investi)      # validation des seuils
    requete = select(Valeur).where(Valeur.type == "action")
    if liste_id:
        ids = [lv.valeur_id for lv in db.exec(select(ListeValeur).where(ListeValeur.liste_id == liste_id))]
        requete = requete.where(col(Valeur.id).in_(ids))
    lignes: list[dict] = []
    resultats: dict[str, dict] = {}
    for valeur in db.exec(requete.order_by(Valeur.nom)):
        regle = _regle(achat, vente, frais, annees_min, fenetre, liquidites, depart_investi, valeur)
        assert valeur.id is not None
        r = simuler(_cours_base(db, valeur.id), regle)
        if r is not None:
            resultats[str(valeur.id)] = r
        details = {"debut": r["debut"], "strategie": r["strategie"], "conserver": r["conserver"],
                   "temps_investi": r["temps_investi"], "operations": len(r["operations"])} if r else {"trop_court": True}
        lignes.append({"id": valeur.id, "nom": valeur.nom, **details})
    return {"resume": agreger(resultats), "valeurs": lignes}
