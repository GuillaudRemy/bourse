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


def test_favoris_pas_de_favori_par_defaut(tmp_path):
    base = tmp_path / "bourse.db"
    _migrer(base, tmp_path / "sauvegardes")
    with sqlite3.connect(base) as c:
        c.execute("UPDATE alembic_version SET version_num = '0010'")
        c.execute("ALTER TABLE valeur DROP COLUMN favori")
        c.execute("INSERT INTO valeur (created_at, symbole, nom, type, source, rupture, echecs) "
                  "VALUES ('2026-01-01', 'AI.PA', 'Air Liquide', 'action', 'yahoo', 0, 0)")
    _migrer(base, tmp_path / "sauvegardes")
    with sqlite3.connect(base) as c:
        assert c.execute("SELECT favori FROM valeur").fetchall() == [(0,)]


def test_cryptos_en_dollars_et_etf_obligataires(tmp_path):
    """Base de la 0.6.0 : BTC-EUR passe en BTC-USD (cours effaces, actualisation relancee), obligations -> ETF."""
    base = tmp_path / "bourse.db"
    _migrer(base, tmp_path / "sauvegardes")
    with sqlite3.connect(base) as c:
        c.execute("UPDATE alembic_version SET version_num = '0009'")
        c.execute("ALTER TABLE valeur DROP COLUMN favori")
        c.execute("INSERT INTO valeur (id, created_at, symbole, nom, type, source, devise, rupture, echecs) VALUES "
                  "(1, '2026-01-01', 'BTC-EUR', 'Bitcoin', 'crypto', 'yahoo', 'EUR', 0, 0),"
                  "(2, '2026-01-01', 'EUNH.DE', 'Oblig', 'obligation', 'yahoo', 'EUR', 0, 0),"
                  "(3, '2026-01-01', 'ETH-EUR', 'Ether', 'crypto', 'yahoo', 'EUR', 0, 0),"
                  "(4, '2026-01-01', 'ETH-USD', 'Ether $', 'crypto', 'yahoo', 'USD', 0, 0)")
        c.execute("INSERT INTO cours (valeur_id, jour, cloture) VALUES (1, '2026-01-02', 100), (3, '2026-01-02', 50)")
        c.execute("INSERT INTO reglage (cle, valeur) VALUES ('derniere_actualisation', '2026-10-29')")
    _migrer(base, tmp_path / "sauvegardes")
    with sqlite3.connect(base) as c:
        assert c.execute("SELECT symbole, devise FROM valeur WHERE id = 1").fetchone() == ("BTC-USD", "USD")
        assert c.execute("SELECT type FROM valeur WHERE id = 2").fetchone() == ("etf",)
        assert c.execute("SELECT symbole FROM valeur WHERE id = 3").fetchone() == ("ETH-EUR",)   # doublon : garde tel quel
        assert c.execute("SELECT valeur_id FROM cours").fetchall() == [(3,)]
        assert c.execute("SELECT COUNT(*) FROM reglage WHERE cle = 'derniere_actualisation'").fetchone()[0] == 0
