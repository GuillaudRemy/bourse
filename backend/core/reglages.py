"""Reglages de l'application, stockes en base (table `reglage`) et modifiables dans l'interface.

Chaque reglage connu est declare ici avec sa valeur par defaut et son explication ;
l'interface affiche cette liste telle quelle.
"""
from dataclasses import asdict, dataclass

from sqlmodel import Session, select

from backend.db.db import engine
from backend.db.schema import Reglage


@dataclass(frozen=True)
class Definition:
    cle: str
    libelle: str
    aide: str
    defaut: str = ""
    secret: bool = False


DEFINITIONS = [
    Definition(
        "actualisation_auto", "Actualisation automatique quotidienne",
        "« oui » : au premier lancement de la journée, toutes les valeurs sont actualisées en tâche de fond. "
        "« non » : uniquement à la demande.",
        defaut="oui",
    ),
    Definition(
        "contact_sec", "E-mail de contact pour la SEC",
        "L'administration américaine (SEC) exige une adresse e-mail dans chaque requête. "
        "Sans elle, les comptes des sociétés américaines ne sont pas téléchargés.",
    ),
]
PAR_CLE = {d.cle: d for d in DEFINITIONS}


# Valeurs internes, memorisees mais non affichees dans les reglages.
INTERNES = {"derniere_actualisation"}


def lire(cle: str) -> str:
    with Session(engine) as db:
        ligne = db.get(Reglage, cle)
    if ligne and ligne.valeur is not None:
        return ligne.valeur
    return PAR_CLE[cle].defaut if cle in PAR_CLE else ""


def ecrire(cle: str, valeur: str | None) -> None:
    with Session(engine) as db:
        ligne = db.get(Reglage, cle) or Reglage(cle=cle)
        ligne.valeur = (valeur or "").strip() or None
        db.add(ligne)
        db.commit()


def tous() -> list[dict]:
    with Session(engine) as db:
        valeurs = {r.cle: r.valeur for r in db.exec(select(Reglage))}
    return [
        {**asdict(d), "valeur": ("••••••" if d.secret and valeurs.get(d.cle) else valeurs.get(d.cle) or "")}
        for d in DEFINITIONS
    ]
