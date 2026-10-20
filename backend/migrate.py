"""Migrations de la base (Alembic).

  · base neuve        : toutes les migrations sont jouees ;
  · base d'avant Alembic (v0.1.x) : elle est reconnue, marquee « 0001 », puis migree ;
  · base a jour       : rien ne se passe.

Rien n'est jamais efface : chaque migration ne fait qu'ajouter.

Usage :
  .venv/bin/python -m backend.migrate                       # mettre a jour
  .venv/bin/python -m backend.migrate nouvelle "message"    # (developpeur) creer une migration
"""
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from backend.core.config import config
from backend.core.sauvegarde import sauvegarder
from backend.db.db import engine

DOSSIER = Path(__file__).parent / "migrations"
BASE_INITIALE = "0001"


def _config() -> Config:
    alembic = Config()
    alembic.set_main_option("script_location", str(DOSSIER))
    return alembic


def main() -> None:
    # Toujours une copie avant de toucher au schema (une par jour au plus).
    copie = sauvegarder()
    if copie:
        print(f"sauvegarde du jour : {copie}")

    Path(config.DB_NAME).parent.mkdir(parents=True, exist_ok=True)
    alembic = _config()
    tables = set(inspect(engine).get_table_names())

    if "valeur" in tables and "alembic_version" not in tables:
        print("base d'avant les migrations : marquee comme version initiale")
        command.stamp(alembic, BASE_INITIALE)
    command.upgrade(alembic, "head")
    print("base a jour")


def nouvelle(message: str) -> None:
    command.revision(_config(), message=message, autogenerate=True)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "nouvelle":
        nouvelle(sys.argv[2])
    else:
        main()
