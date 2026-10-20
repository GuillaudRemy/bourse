from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse

from backend import migrate
from backend.api import fondamentaux, imports, reglages, valeurs
from backend.core.config import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sauvegarde du jour puis migrations : les fondamentaux saisis a la main
    # sont ce qui a le plus de valeur ici.
    migrate.main()
    yield


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
app.include_router(fondamentaux.router, prefix=config.API_PREFIX)
app.include_router(imports.router,      prefix=config.API_PREFIX)
app.include_router(reglages.router,     prefix=config.API_PREFIX)


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
