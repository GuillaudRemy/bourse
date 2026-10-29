"""Couverture et fiabilite des donnees : ce que l'application sait de chaque valeur, et avec quelle confiance."""
import json
from collections import Counter
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, col, select

from backend.analyse import controles, qualite
from backend.db.db import get_session
from backend.db.schema import Correction, Dividende, PieceJointe, Valeur
from backend.services import pdf_service
from backend.services.journal_service import JournalService, dossier_pieces
from backend.services.stockage import charger_cours, charger_dividendes, charger_fondamentaux
from backend.sources import amf
from backend.sources.base import SourceIndisponible

router = APIRouter(tags=["Données"])


def _corrections(db: Session, valeur_id: int | None = None, jours: int = 365) -> list[Correction]:
    requete = select(Correction).where(Correction.created_at >= datetime.now(UTC) - timedelta(days=jours))
    if valeur_id is not None:
        requete = requete.where(Correction.valeur_id == valeur_id)
    return list(db.exec(requete.order_by(col(Correction.created_at).desc())))


@router.get("/donnees/couverture")
def couverture(db: Session = Depends(get_session)):
    """Une ligne par valeur : profondeur des cours et des comptes, sources, identifiants, incidents."""
    dividendes = Counter(d.valeur_id for d in db.exec(select(Dividende)))
    corrections = Counter(c.valeur_id for c in _corrections(db, jours=90))
    lignes = []
    for v in db.exec(select(Valeur).order_by(Valeur.nom)):
        assert v.id is not None
        cours = charger_cours(db, v.id)
        fond = charger_fondamentaux(db, v.id) if v.type == "action" else []
        c = controles.comptes(fond) if fond else None
        sources = sorted({s for f in fond for s in (f.get("sources") or {}).values()})
        lignes.append({
            "id": v.id, "nom": v.nom, "symbole": v.symbole, "type": v.type, "source": v.source,
            "isin": v.isin, "lei": v.lei, "cik": v.cik,
            "cours_debut": cours.index[0].strftime("%Y-%m-%d") if not cours.empty else None,
            "cours_fin": cours.index[-1].strftime("%Y-%m-%d") if not cours.empty else None,
            "seances": len(cours),
            "qualite_cours": qualite.controler(cours, taux=v.type == "taux")["statut"] if not cours.empty else None,
            "comptes_annees": c["annees"] if c else 0, "comptes_premiere": c and c.get("premiere"),
            "comptes_derniere": c and c.get("derniere"), "comptes_score": c and c["score"],
            "comptes_statut": c and c["statut"], "sources_comptes": sources,
            "dividendes": dividendes.get(v.id, 0), "corrections_90j": corrections.get(v.id, 0),
            "echecs": v.echecs, "derniere_erreur": v.derniere_erreur,
            "contre_verification": json.loads(v.infos or "{}").get("contre_verification"),
            "maj_le": v.maj_le.isoformat() if v.maj_le else None,
            "complet_le": v.complet_le.isoformat() if v.complet_le else None,
        })
    return {"valeurs": lignes, "corrections": [
        {"valeur_id": x.valeur_id, "date": x.created_at.isoformat(), "type": x.type, "detail": x.detail}
        for x in _corrections(db, jours=90)[:200]]}


@router.get("/valeurs/{valeur_id}/controles")
def controles_valeur(valeur_id: int, db: Session = Depends(get_session)):
    """Controles de la fiche (onglet Donnees) : comptes, rendement total recalcule, journal des corrections."""
    valeur = db.get(Valeur, valeur_id)
    if not valeur:
        raise HTTPException(404, "Valeur introuvable.")
    return {
        "comptes": controles.comptes(charger_fondamentaux(db, valeur_id)) if valeur.type == "action" else None,
        "rendement_total": controles.rendement_total(charger_cours(db, valeur_id), charger_dividendes(db, valeur_id)),
        "corrections": [{"date": x.created_at.isoformat(), "type": x.type, "detail": x.detail}
                        for x in _corrections(db, valeur_id)],
        "echecs": valeur.echecs, "derniere_erreur": valeur.derniere_erreur,
        "contre_verification": json.loads(valeur.infos or "{}").get("contre_verification"),
    }


@router.get("/valeurs/{valeur_id}/amf")
def documents_amf(valeur_id: int, db: Session = Depends(get_session)):
    """Rapports annuels archives par l'AMF (societes cotees a Paris), et ceux deja ranges dans le journal."""
    valeur = db.get(Valeur, valeur_id)
    if not valeur:
        raise HTTPException(404, "Valeur introuvable.")
    if valeur.type != "action" or not amf.couvre(valeur.symbole, valeur.isin, valeur.pays):
        return {"couvert": False, "documents": []}
    try:
        documents = amf.documents(valeur.nom)
    except SourceIndisponible as e:
        raise HTTPException(502, str(e)) from e
    ranges = {p.nom for p in db.exec(select(PieceJointe).where(PieceJointe.valeur_id == valeur_id))}
    return {"couvert": True, "documents": [d | {"range": _nom_piece(d) in ranges} for d in documents]}


def _nom_piece(document: dict) -> str:
    return f"Rapport annuel {document['annee']} (AMF, {document['fichier']})"


class LectureAmf(BaseModel):
    annee: int


@router.post("/valeurs/{valeur_id}/amf/lire")
def lire_amf(valeur_id: int, demande: LectureAmf, db: Session = Depends(get_session)):
    """Telecharge le rapport annuel d'une annee, le range dans le journal (l'assistant pourra le lire), et en
    extrait les chiffres cles : une PROPOSITION a relire, rien n'est enregistre dans les comptes."""
    valeur = db.get(Valeur, valeur_id)
    if not valeur:
        raise HTTPException(404, "Valeur introuvable.")
    try:
        document = next((d for d in amf.documents(valeur.nom) if d["annee"] == demande.annee), None)
        if document is None:
            raise HTTPException(404, f"Pas de rapport {demande.annee} à l'AMF pour cette société.")
        nom = _nom_piece(document)
        existante = db.exec(select(PieceJointe).where(PieceJointe.valeur_id == valeur_id, PieceJointe.nom == nom)).first()
        if existante:
            contenu = (dossier_pieces() / existante.fichier).read_bytes()
        else:
            contenu = amf.telecharger(document["chemin"])
            JournalService(db).enregistrer_piece(valeur_id, nom, contenu, "application/pdf")
    except SourceIndisponible as e:
        raise HTTPException(502, str(e)) from e
    return pdf_service.analyser_pdf(contenu) | {"document": document}
