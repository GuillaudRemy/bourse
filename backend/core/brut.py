"""Reponses brutes des sources, conservees 30 jours (compressees) a cote de la base.

Pour comprendre une anomalie apres coup (« pourquoi ce BPA a-t-il change mardi ? ») et rejouer un
calcul : on garde exactement ce que chaque site a repondu. Un dossier par jour, purge des dossiers
de plus de 30 jours et plafond de taille total (les plus anciens partent d'abord).
"""
import gzip
import itertools
import re
import shutil
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from backend.core.config import config

JOURS = 30
PLAFOND = 500 * 1024 * 1024              # octets, tous jours confondus
TAILLE_MAX = 50 * 1024 * 1024            # une reponse plus grosse n'est pas gardee (rapports complets)
_compteur = itertools.count()
_verrou = threading.Lock()


def dossier() -> Path:
    return Path(config.DB_NAME).resolve().parent / "brut"


def conserver(source: str, nom: str, contenu: bytes) -> None:
    """Jamais bloquant : une erreur d'ecriture (disque plein, droits) ne doit pas faire echouer une actualisation."""
    if not config.CONSERVER_BRUT or len(contenu) > TAILLE_MAX:
        return
    try:
        jour = dossier() / date.today().isoformat()
        jour.mkdir(parents=True, exist_ok=True)
        propre = re.sub(r"[^A-Za-z0-9._=^-]+", "_", nom)[:120]
        fichier = jour / f"{datetime.now():%H%M%S}-{next(_compteur):05d}-{source}-{propre}.gz"
        fichier.write_bytes(gzip.compress(contenu, compresslevel=6))
    except OSError:
        pass


def purger() -> None:
    """Supprime les jours de plus de 30 jours, puis les plus anciens tant que le plafond est depasse."""
    racine = dossier()
    if not racine.exists():
        return
    with _verrou:
        limite = (date.today() - timedelta(days=JOURS)).isoformat()
        jours = sorted(d for d in racine.iterdir() if d.is_dir())
        for d in [d for d in jours if d.name < limite]:
            shutil.rmtree(d, ignore_errors=True)
        jours = [d for d in jours if d.exists()]
        tailles = {d: sum(f.stat().st_size for f in d.iterdir()) for d in jours}
        while jours[:-1] and sum(tailles[d] for d in jours) > PLAFOND:   # on garde toujours le jour en cours
            shutil.rmtree(jours.pop(0), ignore_errors=True)


def resume() -> dict:
    racine = dossier()
    fichiers = [f for f in racine.glob("*/*.gz")] if racine.exists() else []
    return {"dossier": str(racine), "fichiers": len(fichiers), "taille": sum(f.stat().st_size for f in fichiers),
            "jours": JOURS}
