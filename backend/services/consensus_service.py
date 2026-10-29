"""Historique des previsions des analystes : Yahoo ne montre que leur evolution sur 90 jours ;
un instantane par jour (au plus) permet de suivre les revisions sur des mois."""
from datetime import date

from sqlalchemy import func
from sqlmodel import Session, col, select

from backend.db.schema import ConsensusPrevision, Fondamental


def enregistrer(db: Session, valeur_id: int, donnees: dict | None) -> None:
    """Remplace l'instantane du jour (les previsions bougent dans la journee : on garde la derniere)."""
    if not donnees or not donnees.get("exercices"):
        return
    derniere = db.exec(select(func.max(Fondamental.annee)).where(Fondamental.valeur_id == valeur_id)).first()
    aujourd_hui = date.today()
    objectif = (donnees.get("objectif") or {}).get("mean")
    for e in donnees["exercices"]:
        ligne = db.exec(select(ConsensusPrevision).where(
            ConsensusPrevision.valeur_id == valeur_id, ConsensusPrevision.jour == aujourd_hui,
            ConsensusPrevision.decalage == e["decalage"])).first() or ConsensusPrevision(
            valeur_id=valeur_id, jour=aujourd_hui, decalage=e["decalage"], bpa=e["bpa"])
        ligne.annee = (derniere + 1 if derniere else aujourd_hui.year) + e["decalage"]
        ligne.bpa, ligne.bas, ligne.haut, ligne.objectif = e["bpa"], e.get("bas"), e.get("haut"), objectif
        ligne.analystes = int(e["analystes"]) if e.get("analystes") is not None else None
        db.add(ligne)
    db.commit()


def historique(db: Session, valeur_id: int) -> list[dict]:
    """Instantanes du plus ancien au plus recent : [{jour, annee, bpa, bas, haut, analystes, objectif}]."""
    lignes = db.exec(select(ConsensusPrevision).where(ConsensusPrevision.valeur_id == valeur_id)
                     .order_by(col(ConsensusPrevision.jour), col(ConsensusPrevision.decalage))).all()
    return [{"jour": x.jour.isoformat(), "annee": x.annee, "bpa": x.bpa, "bas": x.bas, "haut": x.haut,
             "analystes": x.analystes, "objectif": x.objectif} for x in lignes]
