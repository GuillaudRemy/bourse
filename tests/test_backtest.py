import numpy as np
import pandas as pd
import pytest

from backend.analyse.backtest import Regle, simuler


def _cours(fin_differente: bool = False):
    jours = pd.bdate_range("2000-01-03", "2025-12-31")
    t = (jours - jours[0]).days / 365.25
    cycle = 0.35 * np.sin(2 * np.pi * t / 6)                   # ecart a la droite : cycle de 6 ans
    serie = pd.Series(20 * np.exp(np.log(1.07) * t + cycle), index=jours)
    if fin_differente:
        serie[serie.index >= "2020-01-01"] *= 3                # un futur tres different
    return serie


def test_pas_de_biais_d_anticipation():
    """Changer les cours FUTURS ne change aucune decision PASSEE."""
    a, b = simuler(_cours(), Regle()), simuler(_cours(fin_differente=True), Regle())
    passees = lambda r: [o for o in r["operations"] if o["jour"] < "2019-12-01"]  # noqa: E731
    assert passees(a) == passees(b) and passees(a)


def test_cycle_regulier_achat_bas_vente_haut():
    r = simuler(_cours(), Regle(seuil_achat=-1, seuil_vente=1, frais=0.0))
    assert r["operations"][0]["type"] == "achat"
    assert all(o["position"] <= -1 for o in r["operations"] if o["type"] == "achat")
    assert r["strategie"]["perte_max"] > r["conserver"]["perte_max"]           # moins de baisse subie
    investi = simuler(_cours(), Regle(seuil_achat=-0.5, seuil_vente=2, depart_investi=True))
    assert investi["temps_investi"] > r["temps_investi"]


def test_historique_trop_court():
    jours = pd.bdate_range("2020-01-01", periods=1000)
    assert simuler(pd.Series(np.linspace(10, 20, 1000), index=jours), Regle(annees_min=10)) is None
    assert Regle().seuil_achat == pytest.approx(-1)
