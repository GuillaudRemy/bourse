"""Une base creee par la v0.1 (avant Alembic) doit etre reprise sans perte."""
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).parent.parent
BASE_V0_1 = Path(__file__).parent / "donnees" / "base_v0_1.db"


def _migrer(base: Path, sauvegardes: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "DB_NAME": str(base), "DOSSIER_SAUVEGARDES": str(sauvegardes)}
    return subprocess.run([sys.executable, "-m", "backend.migrate"], cwd=RACINE, env=env,
                          capture_output=True, text=True, check=True)


def test_base_v0_1_reprise_sans_perte(tmp_path):
    base = tmp_path / "bourse.db"
    shutil.copy(BASE_V0_1, base)

    sortie = _migrer(base, tmp_path / "sauvegardes").stdout
    assert "marquee comme version initiale" in sortie
    assert list((tmp_path / "sauvegardes").glob("bourse-*.db")), "pas de sauvegarde avant migration"

    with sqlite3.connect(base) as c:
        assert c.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        assert c.execute("SELECT notes FROM valeur").fetchone()[0] == "thèse écrite à la main"
        assert c.execute("SELECT annee, bpa, source FROM fondamental").fetchall() == [(2010, 1.5, "manuel")]
        assert c.execute("SELECT COUNT(*) FROM cours").fetchone()[0] == 1

    # Deuxieme passage : rien a faire, rien ne casse.
    assert "marquee" not in _migrer(base, tmp_path / "sauvegardes").stdout


def test_base_neuve(tmp_path):
    base = tmp_path / "neuve.db"
    _migrer(base, tmp_path / "sauvegardes")
    with sqlite3.connect(base) as c:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"valeur", "cours", "fondamental", "alembic_version"} <= tables
