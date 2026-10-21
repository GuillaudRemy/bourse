"""Sauvegarde de la base.

Une copie par jour est prise automatiquement au demarrage de l'API, et on peut
en declencher une a la main a tout moment :

    .venv/bin/python -m backend.core.sauvegarde

Les copies vont dans sauvegardes/ (ou DOSSIER_SAUVEGARDES) ; les 30 plus recentes sont conservees.

Copie externe facultative (reglage « dossier_sauvegarde_externe ») : la copie du jour est aussi
deposee dans un dossier synchronise (Google Drive, OneDrive, Nextcloud…), sous-dossier Bourse/,
10 copies gardees. La base de travail n'y va jamais : une synchronisation pendant une ecriture
peut l'abimer. La copie arrive sous un nom temporaire puis est renommee, pour que l'outil de
synchronisation n'envoie jamais un fichier a moitie ecrit.
"""
import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from backend.core.config import config

RACINE = Path(__file__).parent.parent.parent
DOSSIER = RACINE / config.DOSSIER_SAUVEGARDES   # un chemin absolu remplace RACINE
A_CONSERVER = 30
A_CONSERVER_EXTERNE = 10
_log = logging.getLogger("bourse.sauvegarde")


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
    copier_externe(cible)
    return cible


def dossier_externe() -> Path | None:
    """Dossier externe regle, ou None. Lu en SQL brut : appele avant les migrations."""
    try:
        with sqlite3.connect(RACINE / config.DB_NAME) as connexion:
            ligne = connexion.execute("SELECT valeur FROM reglage WHERE cle = 'dossier_sauvegarde_externe'").fetchone()
    except sqlite3.Error:
        return None
    return Path(ligne[0].strip()).expanduser() / "Bourse" if ligne and (ligne[0] or "").strip() else None


def copier_externe(copie: Path) -> Path | None:
    dossier = dossier_externe()
    if dossier is None:
        return None
    if not dossier.parent.is_dir():          # disque non branche, synchronisation desactivee…
        _log.warning("dossier de sauvegarde externe introuvable : %s", dossier.parent)
        return None
    try:
        dossier.mkdir(exist_ok=True)
        cible = dossier / copie.name
        temporaire = cible.with_suffix(".db.partiel")
        shutil.copy2(copie, temporaire)
        temporaire.replace(cible)
        for ancienne in sorted(dossier.glob("bourse-*.db"), key=lambda p: p.name, reverse=True)[A_CONSERVER_EXTERNE:]:
            ancienne.unlink()
        return cible
    except OSError as e:
        _log.warning("copie externe impossible : %s", e)
        return None


def lister() -> list[dict]:
    """Copies disponibles, locales et externes, de la plus recente a la plus ancienne."""
    copies = []
    for emplacement, dossier in (("locale", DOSSIER), ("externe", dossier_externe())):
        if dossier and dossier.is_dir():
            for f in dossier.glob("*.db"):
                copies.append({"nom": f.name, "emplacement": emplacement, "chemin": str(f), "taille": f.stat().st_size,
                               "date": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="minutes")})
    return sorted(copies, key=lambda c: c["date"], reverse=True)


def restaurer(chemin: Path) -> Path:
    """Remplace le contenu de la base par celui d'une copie, apres une copie de securite.
    Ecrit a travers SQLite : les connexions ouvertes voient aussitot le nouveau contenu."""
    with sqlite3.connect(f"file:{chemin}?mode=ro", uri=True) as verification:
        if verification.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("copie endommagee")
    securite = DOSSIER / f"avant-restauration-{datetime.now():%Y-%m-%d-%H%M%S}.db"
    DOSSIER.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(RACINE / config.DB_NAME) as base, sqlite3.connect(securite) as copie:
        base.backup(copie)
    with sqlite3.connect(f"file:{chemin}?mode=ro", uri=True) as origine, sqlite3.connect(RACINE / config.DB_NAME) as base:
        origine.backup(base)
    return securite


def _purger() -> None:
    copies = sorted(DOSSIER.glob("bourse-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for ancienne in copies[A_CONSERVER:]:
        ancienne.unlink()


if __name__ == "__main__":
    chemin = sauvegarder(manuelle=True)
    print(f"sauvegarde : {chemin}" if chemin else "aucune base a sauvegarder")
