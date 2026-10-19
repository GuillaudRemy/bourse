"""Migration idempotente de la base.

Cree les tables manquantes et ajoute les colonnes apparues au fil des versions,
sans jamais reconstruire ni effacer quoi que ce soit.

Usage : .venv/bin/python -m backend.migrate
"""
import sqlite3
from pathlib import Path
from sqlmodel import SQLModel
from backend.db.db import engine
from backend.core.config import config
import backend.db.schema  # noqa: F401  — enregistre les tables dans les metadonnees

# (table, colonne, definition SQL) — ajoutees si absentes
COLONNES: list[tuple[str, str, str]] = []


def main() -> None:
    Path(config.DB_NAME).parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)   # cree les tables absentes, ne touche pas aux autres

    connexion = sqlite3.connect(config.DB_NAME)
    tables = {r[0] for r in connexion.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    for table, colonne, definition in COLONNES:
        if table not in tables:
            continue
        existantes = [r[1] for r in connexion.execute(f"PRAGMA table_info({table})")]
        if colonne not in existantes:
            connexion.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}")
            print(f"colonne {table}.{colonne} ajoutee")

    connexion.commit()

    for table in sorted(tables):
        total = connexion.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:16} {total:>7} ligne(s)")

    connexion.close()
    print("migration terminee")


if __name__ == "__main__":
    main()
