from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent / ".env"  # backend/.env
# Ecrit par la chaine de publication dans le paquet Windows ; absent en developpement.
_VERSION = Path(__file__).parent.parent.parent / "VERSION"


def _version() -> str:
    return _VERSION.read_text().strip() if _VERSION.exists() else "dev"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    APP_NAME: str = "Bourse"
    APP_VERSION: str = _version()
    DEBUG: bool = False
    API_PREFIX: str = ""

    # Chemin relatif a la racine du projet : la base vit dans un dossier a part,
    # pour que le journal de SQLite reste a cote d'elle (y compris monte dans Docker).
    DB_NAME: str = "donnees/bourse.db"
    DOSSIER_SAUVEGARDES: str = "sauvegardes"

    # Version de bureau (paquet Windows) : le backend sert lui-meme l'interface
    # construite (frontend/dist), et l'API passe sous /api comme derriere nginx.
    DOSSIER_FRONTEND: str = ""
    # Actualisation quotidienne au demarrage (desactivee par les tests).
    ACTUALISATION_AU_DEMARRAGE: bool = True

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8081"

    # Debut par defaut de la droite de regression (methode decrite dans la video) :
    # 2003 pour les actions, apres la bulle internet et l'entree de la Chine a l'OMC ;
    # 1992 pour les indices, debut du regime monetaire moderne.
    DEBUT_ACTIONS: int = 2003
    DEBUT_INDICES: int = 1992

    @property
    def db_url(self) -> str:
        chemin = self.DB_NAME if Path(self.DB_NAME).is_absolute() else f"./{self.DB_NAME}"
        return f"sqlite:///{chemin}"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


@lru_cache
def get_config() -> Config:
    return Config()


config = get_config()
