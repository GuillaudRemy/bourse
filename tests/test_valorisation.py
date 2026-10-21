"""Valorisation (multiples, DCF, DCF inverse) et projection probabiliste."""
import numpy as np
import pandas as pd
import pytest

from backend.analyse import projection, valorisation
from backend.analyse.regression import ajuster
from tests.test_comptes import _comptes


def test_dcf_et_dcf_inverse_coherents():
    h = valorisation.Hypotheses(croissance=0.07, annees=10, terminale=0.02, actualisation=0.09)
    valeur = valorisation._dcf(5.0, h)
    assert valeur > 0
    # Si le cours vaut exactement le DCF, le DCF inverse retrouve la croissance supposee.
    assert valorisation.dcf_inverse(valeur, 5.0, h) == pytest.approx(0.07, abs=1e-4)
    assert valorisation._dcf(5.0, valorisation.Hypotheses(actualisation=0.02, terminale=0.02)) is None


def test_multiples_et_position_historique():
    comptes = _comptes()
    jours = pd.bdate_range("2010-01-01", "2021-12-31")
    cloture = pd.Series(np.linspace(20, 60, len(jours)), index=jours)
    historique = valorisation.multiples_annuels(cloture, comptes)
    assert len(historique) == 12 and historique[-1]["per"] > 0
    tres_cher = valorisation.situer(1000.0, comptes, historique)
    assert tres_cher["historique"]["per"]["cherte"] == 1.0
    assert tres_cher["historique"]["rendement_fcf"]["cherte"] == 1.0     # rendement bas = cher
    modeles = valorisation.modeles(60.0, comptes, {"croissance_dividende_10": 0.08}, valorisation.Hypotheses())
    assert {m["cle"] for m in modeles["modeles"]} == {"dcf", "gordon", "graham"}
    assert modeles["fourchette"]["bas"] <= modeles["fourchette"]["mediane"] <= modeles["fourchette"]["haut"]


def test_projection_revient_vers_la_droite():
    jours = pd.bdate_range("2000-01-03", "2025-12-31")
    rng = np.random.default_rng(3)
    t = (jours - jours[0]).days / 365.25
    ecart = pd.Series(rng.normal(0, 0.01, len(jours))).ewm(alpha=0.01).mean().to_numpy() * 8
    ecart[-60:] = -0.35                        # nettement sous la droite aujourd'hui
    reg = ajuster(pd.Series(10 * np.exp(np.log(1.08) * t + ecart), index=jours))
    p = projection.analyser(reg, reg.fin)
    un_an, dix_ans = p["student"]["horizons"][0], p["student"]["horizons"][-1]
    # Sous la droite : rendement attendu a 1 an superieur a la pente (rattrapage), puis proche d'elle.
    assert un_an["mediane"] > reg.pente
    assert abs(dix_ans["mediane"] - reg.pente) < 0.05
    assert dix_ans["p5"] < dix_ans["mediane"] < dix_ans["p95"]
    assert len(p["cone"]["jours"]) == len(p["cone"]["p50"]) == 120
    assert p["retour"]["episodes"] >= 1
