from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlmodel import SQLModel
from backend.db.db import engine
from backend.core.config import config
from backend.core.sauvegarde import sauvegarder
from backend.api import valeurs, fondamentaux, imports


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Une copie de la base par jour, avant toute chose : les fondamentaux saisis
    # a la main sont ce qui a le plus de valeur ici.
    copie = sauvegarder()
    if copie:
        print(f"sauvegarde du jour : {copie}")

    Path(config.DB_NAME).parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)
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
