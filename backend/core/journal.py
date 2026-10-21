"""Journal d'evenements de l'application, dans le dossier des donnees (fichiers tournants).

Sert au depannage a distance : il ne contient ni cours, ni comptes, ni portefeuille,
seulement ce que fait l'application (demarrage, actualisations, erreurs).
"""
import logging
import logging.handlers
from pathlib import Path

from backend.core.config import config

NOM = "bourse"
_configure = False


def dossier() -> Path:
    d = Path(config.DB_NAME).resolve().parent / "journal"
    d.mkdir(parents=True, exist_ok=True)
    return d


def configurer() -> logging.Logger:
    global _configure
    journal = logging.getLogger(NOM)
    if _configure:
        return journal
    journal.setLevel(logging.INFO)
    fichier = logging.handlers.RotatingFileHandler(dossier() / "bourse.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    fichier.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s : %(message)s"))
    journal.addHandler(fichier)
    for nom in ("uvicorn.error",):                       # erreurs du serveur web aussi
        logging.getLogger(nom).addHandler(fichier)
    _configure = True
    return journal


def journal(module: str) -> logging.Logger:
    return logging.getLogger(f"{NOM}.{module}")
