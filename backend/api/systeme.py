"""A propos et diagnostic."""
import io
import json
import platform
import sys
import zipfile
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

from fastapi import APIRouter, Depends, Response
from sqlalchemy import inspect, text
from sqlmodel import Session

from backend.core import journal, reglages
from backend.core.config import config
from backend.core.sauvegarde import DOSSIER as SAUVEGARDES
from backend.db.db import engine, get_session

router = APIRouter(tags=["Systeme"])
BIBLIOTHEQUES = ["fastapi", "sqlmodel", "sqlalchemy", "alembic", "pandas", "numpy", "yfinance", "pdfplumber",
                 "openpyxl", "uvicorn"]


def _versions() -> dict:
    v = {}
    for nom in BIBLIOTHEQUES:
        try:
            v[nom] = metadata.version(nom)
        except metadata.PackageNotFoundError:
            v[nom] = None
    return v


def _comptages(db: Session) -> dict:
    return {t: db.exec(text(f'SELECT COUNT(*) FROM "{t}"')).one()[0] for t in sorted(inspect(engine).get_table_names())}


@router.get("/a-propos")
def a_propos(db: Session = Depends(get_session)):
    base = Path(config.DB_NAME).resolve()
    return {
        "version": config.APP_VERSION,
        "python": sys.version.split()[0], "systeme": f"{platform.system()} {platform.release()}",
        "base": str(base), "taille_base": base.stat().st_size if base.exists() else 0,
        "sauvegardes": str(SAUVEGARDES),
        "nombre_sauvegardes": len(list(SAUVEGARDES.glob("bourse-*.db"))) if SAUVEGARDES.exists() else 0,
        "journal": str(journal.dossier()),
        "derniere_actualisation": reglages.lire("derniere_actualisation") or None,
        "bibliotheques": _versions(),
        "enregistrements": _comptages(db),
        "depot": "https://github.com/GuillaudRemy/bourse",
    }


@router.get("/diagnostic.zip")
def diagnostic(db: Session = Depends(get_session)):
    """Archive a envoyer pour un depannage : journal, versions, nombre d'enregistrements par table,
    reglages SANS les secrets ni l'e-mail. Aucune donnee de cours, de comptes ou de portefeuille."""
    resume = a_propos(db)
    resume["genere_le"] = datetime.now(UTC).isoformat()
    resume["reglages"] = {r["cle"]: ("(renseigné)" if r["valeur"] and (r["secret"] or "mail" in r["cle"] or "smtp" in r["cle"]
                                                         or "contact" in r["cle"]) else r["valeur"])
                          for r in reglages.tous()}
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("diagnostic.json", json.dumps(resume, ensure_ascii=False, indent=2))
        for fichier in sorted(journal.dossier().glob("bourse.log*")):
            archive.write(fichier, f"journal/{fichier.name}")
    nom = f"bourse-diagnostic-{datetime.now():%Y%m%d-%H%M}.zip"
    return Response(tampon.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{nom}"'})
