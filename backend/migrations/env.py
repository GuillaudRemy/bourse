"""Environnement Alembic : la base est celle de la configuration, le schema celui de SQLModel."""
from alembic import context
from sqlmodel import SQLModel

import backend.db.schema  # noqa: F401  — enregistre les tables dans les metadonnees
from backend.db.db import engine

with engine.connect() as connexion:
    context.configure(
        connection=connexion,
        target_metadata=SQLModel.metadata,
        render_as_batch=True,          # SQLite ne sait pas modifier une colonne : Alembic recopie la table
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
