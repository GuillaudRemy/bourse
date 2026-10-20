"""Sauvegarde de la base.

Une copie par jour est prise automatiquement au demarrage de l'API, et on peut
en declencher une a la main a tout moment :

    .venv/bin/python -m backend.core.sauvegarde

Les copies vont dans sauvegardes/ (ou DOSSIER_SAUVEGARDES) ; les 30 plus recentes sont conservees.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from backend.core.config import config

RACINE = Path(__file__).parent.parent.parent
DOSSIER = RACINE / config.DOSSIER_SAUVEGARDES   # un chemin absolu remplace RACINE
A_CONSERVER = 30


def sauvegarder(manuelle: bool = False) -> Path | None:
    """Copie la base. Automatique : une seule fois par jour. Manuelle : a chaque appel."""
    source = RACINE / config.DB_NAME
    if not source.exists():
        return None

    DOSSIER.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y-%m-%d-%H%M" if manuelle else "%Y-%m-%d")
    cible = DOSSIER / f"bourse-{horodatage}.db"

    if cible.exists():
        return cible          # la sauvegarde du jour est deja faite

    # L'API sqlite garantit une copie coherente meme si une ecriture est en cours.
    with sqlite3.connect(source) as origine, sqlite3.connect(cible) as copie:
        origine.backup(copie)

    _purger()
    return cible


def _purger() -> None:
    copies = sorted(DOSSIER.glob("bourse-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for ancienne in copies[A_CONSERVER:]:
        ancienne.unlink()


if __name__ == "__main__":
    chemin = sauvegarder(manuelle=True)
    print(f"sauvegarde : {chemin}" if chemin else "aucune base a sauvegarder")
