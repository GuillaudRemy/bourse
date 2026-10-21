"""Lecture et ecriture en masse des cours et des fondamentaux."""
import json
import math
from datetime import date

import pandas as pd
from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session, func, select

from backend.db.champs import CLES, PAR_ACTION_CLES, PRIORITE
from backend.db.schema import Cours, Division, Evenement, Fondamental, TauxChange
from backend.sources.xbrl import DELAI_PUBLICATION, ajuster_divisions, facteur_divisions

COLONNES_COURS = ["ouverture", "haut", "bas", "cloture", "ajuste", "volume"]
# Saisies humaines : publiees « telles que declarees », a ajuster des divisions a la lecture.
SAISIES = {"manuel", "import", "pdf"}
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


def provenance(ligne: Fondamental) -> dict[str, str]:
    """Source de chaque case. Les lignes d'avant la provenance par case heritent de `source`."""
    if ligne.sources:
        return json.loads(ligne.sources)
    return {c: ligne.source for c in CLES if getattr(ligne, c) is not None}


def enregistrer_fondamentaux(db: Session, valeur_id: int, annees: dict[int, dict], source: str) -> int:
    """Fusionne des comptes annuels case par case : une case n'est remplacee que par une
    source au moins aussi fiable (champs.PRIORITE). Une saisie manuelle n'est donc jamais
    ecrasee par une actualisation, mais une source officielle (SEC, ESEF) remplace Yahoo."""
    rang = PRIORITE[source]
    existantes = {f.annee: f for f in db.exec(select(Fondamental).where(Fondamental.valeur_id == valeur_id))}
    total = 0
    for annee, champs in annees.items():
        champs = {c: v for c, v in ((c, _nombre(champs.get(c))) for c in CLES if c in champs) if v is not None}
        if not champs:
            continue
        ligne = existantes.get(annee)
        if ligne is None:
            ligne = Fondamental(valeur_id=valeur_id, annee=annee, source=source)
            db.add(ligne)
            existantes[annee] = ligne
        origine = provenance(ligne)
        modifiee = False
        for cle, valeur in champs.items():
            actuelle = origine.get(cle)
            if actuelle is None or PRIORITE.get(actuelle, 0) <= rang:
                setattr(ligne, cle, valeur)
                origine[cle] = source
                modifiee = True
        if modifiee:
            ligne.sources = json.dumps(origine)
            ligne.source = max(origine.values(), key=lambda s: PRIORITE.get(s, 0))
            total += 1
    return total


def enregistrer_divisions(db: Session, valeur_id: int, divisions: list[tuple]) -> None:
    """Remplace la liste des divisions d'actions de la valeur."""
    for ancienne in db.exec(select(Division).where(Division.valeur_id == valeur_id)):
        db.delete(ancienne)
    db.flush()
    for jour, ratio in sorted(set(divisions)):
        db.add(Division(valeur_id=valeur_id, jour=jour, ratio=ratio))


def charger_divisions(db: Session, valeur_id: int) -> list[tuple[date, float]]:
    return [(d.jour, d.ratio) for d in db.exec(
        select(Division).where(Division.valeur_id == valeur_id).order_by(Division.jour))]


def charger_fondamentaux(db: Session, valeur_id: int) -> list[dict]:
    """Comptes annuels prets pour l'analyse : postes par action des saisies et imports
    manuels ramenes a la base d'actions actuelle (SEC et ESEF le sont deja, Yahoo aussi)."""
    divisions = charger_divisions(db, valeur_id)
    resultat = []
    for ligne in db.exec(select(Fondamental).where(Fondamental.valeur_id == valeur_id).order_by(Fondamental.annee)):
        origine = provenance(ligne)
        valeurs = {c: getattr(ligne, c) for c in CLES}
        publication = date(ligne.annee, 12, 31) + DELAI_PUBLICATION
        facteur = facteur_divisions(divisions, publication)
        ajustes = []
        if facteur != 1:
            for cle in [*PAR_ACTION_CLES, "nombre_actions"]:
                if valeurs[cle] is not None and origine.get(cle) in SAISIES:
                    valeurs[cle] = ajuster_divisions({cle: valeurs[cle]}, facteur)[cle]
                    ajustes.append(cle)
        # Postes reconstitues quand la source ne les publie pas, signales « calcul ».
        if valeurs["ebitda"] is None and valeurs["ebit"] is not None and valeurs["amortissements"] is not None:
            valeurs["ebitda"] = valeurs["ebit"] + valeurs["amortissements"]
            origine = {**origine, "ebitda": "calcul"}
        resultat.append({"annee": ligne.annee, **valeurs, "source": ligne.source, "sources": origine,
                         "ajustes": ajustes})
    return resultat


def enregistrer_taux(db: Session, devise: str, serie: pd.Series) -> int:
    lignes = [{"devise": devise, "jour": jour.date(), "taux": float(v)} for jour, v in serie.items()]
    table = TauxChange.__table__
    for i in range(0, len(lignes), PAQUET):
        requete = insert(table).values(lignes[i:i + PAQUET])
        db.exec(requete.on_conflict_do_update(index_elements=["devise", "jour"], set_={"taux": requete.excluded.taux}))
    return len(lignes)


def charger_taux(db: Session, devise: str) -> pd.Series:
    lignes = db.exec(select(TauxChange.jour, TauxChange.taux).where(TauxChange.devise == devise)
                     .order_by(TauxChange.jour)).all()
    return pd.Series([t for _, t in lignes], index=pd.to_datetime([j for j, _ in lignes]), dtype=float)


def dernier_taux(db: Session, devise: str) -> date | None:
    return db.exec(select(func.max(TauxChange.jour)).where(TauxChange.devise == devise)).first()


def enregistrer_evenements(db: Session, valeur_id: int, evenements: list[tuple]) -> None:
    """Remplace les evenements a venir (les dates changent) et ajoute les passes manquants."""
    aujourd_hui = date.today()
    for e in db.exec(select(Evenement).where(Evenement.valeur_id == valeur_id, Evenement.jour >= aujourd_hui)):
        db.delete(e)
    db.flush()
    existants = {(e.jour, e.type) for e in db.exec(select(Evenement).where(Evenement.valeur_id == valeur_id))}
    for jour, type_, detail in sorted(set(evenements)):
        if (jour, type_) not in existants:
            db.add(Evenement(valeur_id=valeur_id, jour=jour, type=type_, detail=detail))
            existants.add((jour, type_))
