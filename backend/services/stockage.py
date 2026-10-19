"""Lecture et ecriture en masse des cours et des fondamentaux."""
import math
import pandas as pd
from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session, select
from backend.db.schema import Cours, Fondamental

COLONNES_COURS = ["ouverture", "haut", "bas", "cloture", "ajuste", "volume"]
CHAMPS_FONDAMENTAUX = ["bpa", "benefice_net", "chiffre_affaires", "dividende"]
PAQUET = 2000   # SQLite limite le nombre de parametres par requete


def _nombre(v):
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def enregistrer_cours(db: Session, valeur_id: int, df: pd.DataFrame) -> int:
    """Insere ou remplace les seances de `df` (colonne `jour` + COLONNES_COURS)."""
    lignes = [
        {"valeur_id": valeur_id, "jour": ligne["jour"],
         **{c: _nombre(ligne.get(c)) for c in COLONNES_COURS}}
        for ligne in df.to_dict("records")
        if _nombre(ligne.get("cloture")) is not None
    ]
    table = Cours.__table__
    for i in range(0, len(lignes), PAQUET):
        requete = insert(table).values(lignes[i:i + PAQUET])
        requete = requete.on_conflict_do_update(
            index_elements=["valeur_id", "jour"],
            set_={c: requete.excluded[c] for c in COLONNES_COURS},
        )
        db.exec(requete)
    return len(lignes)


def charger_cours(db: Session, valeur_id: int) -> pd.DataFrame:
    """Cours d'une valeur, indexes par date (DatetimeIndex), du plus ancien au plus recent."""
    lignes = db.exec(
        select(Cours.jour, *[getattr(Cours, c) for c in COLONNES_COURS])
        .where(Cours.valeur_id == valeur_id)
        .order_by(Cours.jour)
    ).all()
    df = pd.DataFrame(lignes, columns=["jour", *COLONNES_COURS])
    df.index = pd.to_datetime(df.pop("jour"))
    return df.astype(float)


def enregistrer_fondamentaux(
    db: Session, valeur_id: int, annees: dict[int, dict], source: str, ecraser: bool = True,
) -> int:
    """Fusionne les donnees annuelles. Avec `ecraser=False` (actualisation Yahoo),
    une annee saisie ou importee a la main est laissee intacte."""
    existantes = {
        f.annee: f for f in db.exec(select(Fondamental).where(Fondamental.valeur_id == valeur_id))
    }
    total = 0
    for annee, champs in annees.items():
        champs = {c: _nombre(champs.get(c)) for c in CHAMPS_FONDAMENTAUX if c in champs}
        if not any(v is not None for v in champs.values()):
            continue
        ligne = existantes.get(annee)
        if ligne is None:
            db.add(Fondamental(valeur_id=valeur_id, annee=annee, source=source, **champs))
        elif ecraser or ligne.source == "yahoo":
            for cle, valeur in champs.items():
                if valeur is not None:
                    setattr(ligne, cle, valeur)
            ligne.source = source
        else:
            # Ligne manuelle : on ne comble que les cases vides.
            for cle, valeur in champs.items():
                if valeur is not None and getattr(ligne, cle) is None:
                    setattr(ligne, cle, valeur)
        total += 1
    return total
