"""Univers (composition des indices) et listes personnelles."""
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.db.db import get_session
from backend.db.schema import Liste, ListeValeur, Valeur
from backend.services import alertes_service, taches
from backend.sources import univers
from backend.sources.base import SourceIndisponible

router = APIRouter(tags=["Univers et listes"])


@router.get("/univers")
def liste_univers():
    return univers.catalogue()


@router.get("/univers/{cle}")
def composition(cle: str, db: Session = Depends(get_session)):
    try:
        membres = univers.composition(cle)
    except SourceIndisponible as e:
        raise HTTPException(502, str(e)) from e
    suivies = {v.symbole: v.id for v in db.exec(select(Valeur))}
    return [{**m, "valeur_id": suivies.get(m["symbole"])} for m in membres]


class Import(BaseModel):
    symboles: list[str] = Field(min_length=1, max_length=600)
    liste: str | None = None          # ranger aussi les valeurs dans cette liste (creee si besoin)


@router.post("/univers/{cle}/importer")
def importer(cle: str, data: Import, db: Session = Depends(get_session)):
    """Cree les valeurs demandees (sans attendre), puis lance leur telechargement en tache de fond."""
    try:
        membres = {m["symbole"]: m for m in univers.composition(cle)}
    except SourceIndisponible as e:
        raise HTTPException(502, str(e)) from e
    creees, ids = [], []
    existantes = {v.symbole: v.id for v in db.exec(select(Valeur))}
    for symbole in data.symboles:
        if symbole in existantes:
            ids.append(existantes[symbole])
            continue
        m = membres.get(symbole)
        if not m:
            continue
        # Creation immediate (sans interroger Yahoo valeur par valeur : 500 valeurs = 8 minutes) ;
        # la fiche, les cours et les comptes arrivent avec l'actualisation en tache de fond.
        valeur = Valeur(symbole=symbole, nom=m["nom"], type="action", source="yahoo", cik=m.get("cik"),
                        secteur=None)
        db.add(valeur)
        db.commit()
        db.refresh(valeur)
        alertes_service.creer_par_defaut(db, valeur)
        db.commit()
        creees.append(symbole)
        ids.append(valeur.id)
    if data.liste:
        _ajouter(db, _liste(db, data.liste), ids)
    taches.lancer()
    return {"creees": len(creees), "deja_suivies": len(ids) - len(creees),
            "message": f"{len(creees)} valeur(s) ajoutée(s) ; téléchargement des données en arrière-plan."}


# ── Listes personnelles ──
class Nom(BaseModel):
    nom: str = Field(min_length=1, max_length=60)


class Ids(BaseModel):
    valeur_ids: list[int]


def _liste(db: Session, nom: str) -> Liste:
    liste = db.exec(select(Liste).where(Liste.nom == nom.strip())).first()
    if not liste:
        liste = Liste(nom=nom.strip())
        db.add(liste)
        db.commit()
        db.refresh(liste)
    return liste


def _ajouter(db: Session, liste: Liste, ids: Sequence[int | None]) -> None:
    presentes = {lv.valeur_id for lv in db.exec(select(ListeValeur).where(ListeValeur.liste_id == liste.id))}
    for vid in set(ids) - presentes:
        if vid is not None and liste.id is not None and db.get(Valeur, vid) is not None:
            db.add(ListeValeur(liste_id=liste.id, valeur_id=vid))
    db.commit()


@router.get("/listes")
def listes(db: Session = Depends(get_session)):
    resultat = []
    for liste in db.exec(select(Liste).order_by(Liste.nom)):
        ids = [lv.valeur_id for lv in db.exec(select(ListeValeur).where(ListeValeur.liste_id == liste.id))]
        resultat.append({"id": liste.id, "nom": liste.nom, "valeur_ids": ids})
    return resultat


@router.post("/listes", status_code=201)
def creer_liste(data: Nom, db: Session = Depends(get_session)):
    if db.exec(select(Liste).where(Liste.nom == data.nom.strip())).first():
        raise HTTPException(409, "Cette liste existe déjà.")
    return _liste(db, data.nom).model_dump()


@router.put("/listes/{liste_id}")
def renommer_liste(liste_id: int, data: Nom, db: Session = Depends(get_session)):
    liste = db.get(Liste, liste_id) or _introuvable()
    liste.nom = data.nom.strip()
    db.commit()
    return liste.model_dump()


@router.delete("/listes/{liste_id}", status_code=204)
def supprimer_liste(liste_id: int, db: Session = Depends(get_session)):
    db.delete(db.get(Liste, liste_id) or _introuvable())
    db.commit()


@router.post("/listes/{liste_id}/valeurs", status_code=204)
def ajouter_valeurs(liste_id: int, data: Ids, db: Session = Depends(get_session)):
    _ajouter(db, db.get(Liste, liste_id) or _introuvable(), data.valeur_ids)


@router.delete("/listes/{liste_id}/valeurs/{valeur_id}", status_code=204)
def retirer_valeur(liste_id: int, valeur_id: int, db: Session = Depends(get_session)):
    lien = db.exec(select(ListeValeur).where(ListeValeur.liste_id == liste_id, ListeValeur.valeur_id == valeur_id)).first()
    if lien:
        db.delete(lien)
        db.commit()


def _introuvable():
    raise HTTPException(404, "Liste introuvable.")
