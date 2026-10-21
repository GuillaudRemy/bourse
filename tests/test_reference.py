"""Cas de reference figes : comptes reels d'Apple publies a la SEC (domaine public).

Deux sortes de verifications : des valeurs recalculees a la main depuis le 10-K (independantes
du code), et un instantane des scores qui doit bouger seulement si on change la methode exprès.
"""
import json
from pathlib import Path

import pytest

from backend.analyse import ratios, scores

DONNEES = json.loads((Path(__file__).parent / "donnees" / "reference_apple_sec.json").read_text())["comptes"]


@pytest.fixture(scope="module")
def apple():
    comptes = [c for c in DONNEES if c.get("chiffre_affaires") is not None or c.get("benefice_net") is not None]
    annuels = ratios.annuels(comptes)
    return comptes, annuels, ratios.synthese(comptes, annuels)


def test_ratios_2025_recalcules_a_la_main(apple):
    _, annuels, _ = apple
    r = annuels[-1]
    assert r["annee"] == 2025
    assert r["marge_brute"] == pytest.approx(195_201 / 416_161)
    assert r["marge_operationnelle"] == pytest.approx(133_050 / 416_161)
    assert r["marge_nette"] == pytest.approx(112_010 / 416_161)
    assert r["fcf"] == pytest.approx((111_482 - 12_715) * 1e6)
    assert r["dette_nette"] == pytest.approx((90_678 - 35_934) * 1e6)
    # EBITDA non publie par la SEC : resultat operationnel + amortissements.
    assert r["dette_nette_ebitda"] == pytest.approx((90_678 - 35_934) / (133_050 + 11_698))
    assert r["liquidite"] == pytest.approx(147_957 / 165_631)
    assert r["dilution"] < 0                                     # rachats d'actions


def test_synthese_et_scores_instantane(apple):
    comptes, _, synthese = apple
    assert synthese["annees_comptes"] == 19
    assert synthese["croissance_bpa_10"] == pytest.approx(0.1608, abs=1e-4)
    assert synthese["croissance_ca_10"] == pytest.approx(0.0821, abs=1e-4)
    assert synthese["roic_moyen_5"] == pytest.approx(0.6672, abs=1e-4)
    assert synthese["dividende_sans_baisse"] == 15
    piotroski = [scores.piotroski(comptes[i - 2] if i >= 2 else {}, comptes[i - 1], comptes[i])["score"]
                 for i in range(len(comptes) - 5, len(comptes))]
    assert piotroski == [7, 6, 7, 7, 8]
    beneish = scores.beneish(comptes[-2], comptes[-1])
    assert beneish["m"] == pytest.approx(-2.2949, abs=1e-4) and not beneish["vigilance"]
    note = scores.note_maison(synthese)
    assert note["note"] >= 90 and note["couverture"] == 100
