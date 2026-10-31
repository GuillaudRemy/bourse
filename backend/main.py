import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse

from backend import migrate
from backend.api import (
    assistant,
    donnees,
    fondamentaux,
    imports,
    journal,
    outils,
    portefeuille,
    recherche,
    reglages,
    suivi,
    systeme,
    univers,
    valeurs,
)
from backend.core import brut
from backend.core import journal as journal_evenements
from backend.core.config import config
from backend.services import taches


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sauvegarde du jour puis migrations : les fondamentaux saisis a la main
    # sont ce qui a le plus de valeur ici.
    journal_evenements.configurer().info("demarrage de Bourse %s", config.APP_VERSION)
    migrate.main()
    brut.purger()
    arret = threading.Event()
    if config.ACTUALISATION_AU_DEMARRAGE:
        taches.lancer_si_besoin()
        threading.Thread(target=taches.veiller, args=(arret,), daemon=True, name="veille-actualisation").start()
    yield
    arret.set()


app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    lifespan=lifespan,
)

# Les series de cours pesent lourd en JSON : la compression les divise par 5 environ.
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(valeurs.router,      prefix=config.API_PREFIX)
app.include_router(outils.router,       prefix=config.API_PREFIX)
app.include_router(donnees.router,      prefix=config.API_PREFIX)
app.include_router(fondamentaux.router, prefix=config.API_PREFIX)
app.include_router(imports.router,      prefix=config.API_PREFIX)
app.include_router(reglages.router,     prefix=config.API_PREFIX)
app.include_router(journal.router,      prefix=config.API_PREFIX)
app.include_router(journal.annotations, prefix=config.API_PREFIX)
app.include_router(portefeuille.router, prefix=config.API_PREFIX)
app.include_router(suivi.router,        prefix=config.API_PREFIX)
app.include_router(univers.router,      prefix=config.API_PREFIX)
app.include_router(recherche.router,    prefix=config.API_PREFIX)
app.include_router(systeme.router,      prefix=config.API_PREFIX)
app.include_router(assistant.router,    prefix=config.API_PREFIX)


@app.get("/health")
def health():
    return {"status": "ok", "version": config.APP_VERSION}


if config.DOSSIER_FRONTEND:
    _DIST = Path(config.DOSSIER_FRONTEND).resolve()

    @app.get("/{chemin:path}", include_in_schema=False)
    def interface(chemin: str):
        """Fichiers de l'interface ; toute autre adresse sert index.html (application monopage)."""
        if chemin.startswith(config.API_PREFIX.strip("/") + "/"):
            raise HTTPException(404, "Route inconnue.")
        fichier = (_DIST / chemin).resolve()
        if chemin and fichier.is_file() and fichier.is_relative_to(_DIST):
            return FileResponse(fichier)
        return FileResponse(_DIST / "index.html")
