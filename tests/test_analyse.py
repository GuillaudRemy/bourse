import numpy as np
import pandas as pd

from backend.analyse import fiabilite
from backend.analyse import indicateurs as ind
from backend.analyse.regression import ajuster, zone


def test_regression_retrouve_la_pente(cours_synthetiques):
    reg = ajuster(cours_synthetiques)
    assert abs(reg.pente - 0.10) < 0.01
    assert 0 < reg.ecart_type < 0.5
    assert reg.r2 > 0.9
    assert abs(sum(reg.repartition().values()) - 1) < 1e-9


def test_regression_refuse_un_historique_trop_court():
    assert ajuster(pd.Series([1.0, 2.0], index=pd.bdate_range("2024-01-01", periods=2))) is None


def test_zones():
    assert zone(-2.5)[0] == "opportunite_manifeste"
    assert zone(-1.5)[0] == "sous_evalue"
    assert zone(0)[0] == "normal"
    assert zone(1.5)[0] == "surevalue"
    assert zone(2.5)[0] == "surevaluation_manifeste"


def test_indicateurs(cours_synthetiques):
    rsi = ind.rsi(cours_synthetiques).dropna()
    assert rsi.between(0, 100).all()
    mm = ind.moyenne_mobile(cours_synthetiques, 20)
    assert np.isclose(mm.iloc[-1], cours_synthetiques.tail(20).mean())
    assert mm.iloc[:19].isna().all()
    assert ind.perte_maximale(cours_synthetiques)[0] < 0
    assert ind.signaux(cours_synthetiques, ind.moyenne_mobile(cours_synthetiques, 50),
                       ind.moyenne_mobile(cours_synthetiques, 200), ind.rsi(cours_synthetiques))


def test_fiabilite_per_stable(cours_synthetiques):
    """Si le BPA croit comme le cours, le PER est stable : la pente est saine."""
    reg = ajuster(cours_synthetiques)
    moyennes = cours_synthetiques.groupby(cours_synthetiques.index.year).mean()
    fond = [{"annee": int(a), "bpa": float(v) / 15} for a, v in moyennes.items()]
    verif = fiabilite.per(reg, cours_synthetiques, fond)
    assert verif["statut"] == "ok"
    assert abs(verif["details"]["derive_per"]) < 0.01
    assert fiabilite.historique(reg)["statut"] == "ok"


def test_champs_alignes_sur_le_schema():
    """Chaque poste du catalogue est une colonne de la table, et inversement."""
    from backend.db.champs import CLES
    from backend.db.schema import Fondamental
    colonnes = set(Fondamental.model_fields) - {"id", "annee", "source", "sources", "valeur_id", "valeur"}
    assert colonnes == set(CLES)


def test_controle_qualite(cours_synthetiques):
    from backend.analyse.qualite import controler
    propre = pd.DataFrame({"cloture": cours_synthetiques, "ajuste": cours_synthetiques * 0.9})
    assert controler(propre)["statut"] == "ok"

    abime = propre.copy()
    abime.iloc[1000, 0] *= 3                   # pic aussitot annule
    abime.iloc[3000:, 0] /= 2                  # division mal ajustee
    abime = abime.drop(abime.index[4000:4040])  # deux mois sans cotation
    rapport = controler(abime)
    types = {a["type"] for a in rapport["anomalies"]}
    assert rapport["statut"] == "alerte"
    assert {"pic", "saut", "trou"} <= types
    assert any("division" in a["texte"] for a in rapport["anomalies"])


def test_avertissement_indice_prix():
    from backend.analyse.indices import avertissement
    assert avertissement("^FCHI", "CAC 40", "indice")["symbole"] == "CAC.PA"
    assert avertissement("^SP500TR", "S&P 500 (TR)", "indice") is None
    assert avertissement("^990100-USD-NETR", "MSCI WORLD NETR USD", "indice") is None
    assert avertissement("AI.PA", "Air Liquide", "action") is None
    assert avertissement("^N225", "Nikkei 225", "indice")["symbole"] is None


def test_capitalisation_en_euros():
    """Cours x actions, converti en euros ; cotation en pence : capitalisation en livres (comme Yahoo)."""
    import json
    from datetime import date

    import pytest
    from fastapi.testclient import TestClient
    from sqlmodel import Session

    from backend.db.db import engine
    from backend.db.schema import TauxChange, Valeur
    from backend.main import app  # noqa: F401  (cree la base)
    from backend.services.analyse_service import AnalyseService
    with TestClient(app), Session(engine) as db:
        db.add(TauxChange(devise="GBP", jour=date(2026, 10, 27), taux=0.85))
        db.add(TauxChange(devise="USD", jour=date(2026, 10, 27), taux=1.25))
        londres = Valeur(symbole="CAPI.L", nom="Londres", devise="GBp", infos=json.dumps({"actions_en_circulation": 2e9}))
        newyork = Valeur(symbole="CAPI", nom="New York", devise="USD", infos=json.dumps({"capitalisation": 5e12}))
        paris = Valeur(symbole="CAPI.PA", nom="Paris", devise="EUR", infos=json.dumps({"actions_en_circulation": 1e6}))
        indice = Valeur(symbole="^CAPI", nom="Indice", type="indice", devise="EUR")
        db.add_all([londres, newyork, paris, indice])
        db.commit()
        service = AnalyseService(db)
        assert service._capitalisation_eur(londres, 4800) == pytest.approx(2e9 * 48 / 0.85)   # 4 800 pence = 48 livres
        assert service._capitalisation_eur(newyork, 300) == pytest.approx(5e12 / 1.25)          # repli : capitalisation Yahoo
        assert service._capitalisation_eur(paris, 50) == pytest.approx(5e7)
        assert service._capitalisation_eur(indice, 8000) is None


def test_dates_de_la_droite_strictement_croissantes(csv_cours):
    """Pour chaque longueur d'historique (dernier jour dans l'echantillon ou non), aucune date en double."""
    from fastapi.testclient import TestClient

    from backend.main import app
    lignes = csv_cours.decode().splitlines()
    with TestClient(app) as client:
        for retire in range(5):
            vid = client.post("/valeurs", json={"symbole": f"DATES{retire}", "source": "import"}).json()["id"]
            contenu = "\n".join(lignes[:len(lignes) - retire]).encode()
            client.post(f"/valeurs/{vid}/import/cours", files={"fichier": ("c.csv", contenu)})
            jours = client.get(f"/valeurs/{vid}/analyse").json()["regression"]["droite"]["jours"]
            assert all(a < b for a, b in zip(jours, jours[1:], strict=False)), retire
