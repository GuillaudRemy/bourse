"""Ajoute les valeurs prises en exemple dans la video (a lancer une fois, base vide ou non).

Usage : .venv/bin/python -m backend.seed
"""
from fastapi import HTTPException
from sqlmodel import SQLModel, Session
from backend.db.db import engine
from backend.models.valeur import ValeurCreate
from backend.services.valeur_service import ValeurService

EXEMPLES = [
    "AI.PA",    # Air Liquide : action calme, couloir etroit
    "AM.PA",    # Dassault Aviation : plus agitee
    "OPM.PA",   # OPmobility (ex-Plastic Omnium) : cyclique, couloir tres large
    "OR.PA",    # L'Oreal : PER structurellement eleve
    "^FCHI",    # CAC 40
    "^GSPC",    # S&P 500
]


def main() -> None:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        service = ValeurService(session)
        for symbole in EXEMPLES:
            try:
                valeur = service.create(ValeurCreate(symbole=symbole))
                print(f"+ {valeur.symbole:8} {valeur.nom}")
            except HTTPException as e:
                session.rollback()
                print(f"  {symbole:8} {e.detail}")


if __name__ == "__main__":
    main()
