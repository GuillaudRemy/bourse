import os
import tempfile
from pathlib import Path

# Base et sauvegardes jetables, fixees avant tout import du backend (la config est lue a l'import).
_TMP = Path(tempfile.mkdtemp(prefix="bourse-tests-"))
os.environ["DB_NAME"] = str(_TMP / "test.db")
os.environ["DOSSIER_SAUVEGARDES"] = str(_TMP / "sauvegardes")
os.environ["ACTUALISATION_AU_DEMARRAGE"] = "false"
os.environ["NOTIFICATIONS"] = "false"
os.environ["CONSERVER_BRUT"] = "false"

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def cours_synthetiques():
    """24 ans de cours : +10 %/an en tendance, bruit autour de la droite, seances ouvrees."""
    jours = pd.bdate_range("2002-01-02", "2025-12-31")
    rng = np.random.default_rng(42)
    t = (jours - jours[0]).days / 365.25
    bruit = pd.Series(rng.normal(0, 0.01, len(jours))).ewm(alpha=0.02).mean().to_numpy() * 10
    return pd.Series(50 * np.exp(np.log(1.10) * t + bruit), index=jours)


@pytest.fixture
def csv_cours(cours_synthetiques):
    """Le meme historique au format d'un export francais (point-virgule, virgule decimale)."""
    lignes = ["Date;Clôture;Volume"]
    for jour, valeur in cours_synthetiques.items():
        lignes.append(f"{jour:%d/%m/%Y};{valeur:.4f};1 000".replace(".", ","))
    return "\n".join(lignes).encode("utf-8")
