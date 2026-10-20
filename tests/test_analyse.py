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
