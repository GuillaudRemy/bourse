"""Ratios, scores, robustesse de la pente et confrontation cours / benefices."""
import numpy as np
import pandas as pd
import pytest

from backend.analyse import benefices, ratios, robustesse, scores


def _comptes(annees=12, croissance=0.08):
    """Entreprise saine et reguliere : CA +8 %/an, marge 20 %, peu de dette, actions en baisse."""
    lignes = []
    for i in range(annees):
        ca = 1000 * (1 + croissance) ** i
        lignes.append({
            "annee": 2010 + i, "chiffre_affaires": ca, "marge_brute": ca * 0.5, "frais_generaux": ca * 0.2,
            "ebit": ca * 0.2, "amortissements": ca * 0.05, "ebitda": ca * 0.25, "charges_interets": ca * 0.005,
            "benefice_net": ca * 0.15, "nombre_actions": 100 * 0.99 ** i, "bpa": ca * 0.15 / (100 * 0.99 ** i),
            "dividende": ca * 0.06 / 100, "total_actif": ca * 1.5, "actifs_courants": ca * 0.6,
            "tresorerie": ca * 0.1, "creances_clients": ca * 0.15, "immobilisations_corporelles": ca * 0.5,
            "passifs_courants": ca * 0.3, "total_passif": ca * 0.7, "dette_financiere": ca * 0.3,
            "dette_long_terme": ca * 0.25, "capitaux_propres": ca * 0.8, "resultats_non_distribues": ca * 0.5,
            "flux_operationnel": ca * 0.19, "capex": ca * 0.05, "dividendes_verses": ca * 0.06,
            "rachats_actions": ca * 0.01,
        })
    return lignes


def test_ratios_et_synthese():
    comptes = _comptes()
    annuels = ratios.annuels(comptes)
    dernier = annuels[-1]
    assert dernier["marge_operationnelle"] == pytest.approx(0.20)
    assert dernier["dette_nette_ebitda"] == pytest.approx(0.2 / 0.25)
    assert dernier["dilution"] == pytest.approx(-0.01)
    assert annuels[0]["dilution"] is None                       # pas d'annee precedente
    s = ratios.synthese(comptes, annuels)
    assert s["croissance_ca_10"] == pytest.approx(0.08, abs=1e-6)
    assert s["stabilite_marge_10"] == pytest.approx(0, abs=1e-9)
    assert s["annees_comptes"] == 12
    note = scores.note_maison(s)
    assert note["note"] >= 70 and not note["provisoire"]


def test_ratio_absent_reste_absent():
    comptes = [{"annee": 2020, "chiffre_affaires": 100.0, "benefice_net": None}]
    assert ratios.annuels(comptes)[0]["marge_nette"] is None


def test_scores():
    c = _comptes()
    p = scores.piotroski(c[-3], c[-2], c[-1])
    criteres = {x["nom"]: x["ok"] for x in p["criteres"]}
    # Ratios constants d'une annee sur l'autre : les criteres « en hausse » sont faux, les autres vrais.
    assert p["sur"] == 9 and p["score"] == 5
    assert criteres["Pas de dilution"] and criteres["Bénéfice de qualité (flux > bénéfice)"]
    assert criteres["Marge brute en hausse"] is False
    z = scores.altman(c[-1], capitalisation=c[-1]["chiffre_affaires"] * 3)
    assert z["zone"] == "sûre"
    m = scores.beneish(c[-2], c[-1])
    assert m["m"] is not None and not m["vigilance"]


def test_robustesse_detecte_une_rupture():
    jours = pd.bdate_range("2000-01-03", "2025-12-31")
    t = (jours - jours[0]).days / 365.25
    # +15 %/an jusqu'en 2013, puis -5 %/an : un changement de regime franc.
    log = np.where(t < 13, np.log(1.15) * t, np.log(1.15) * 13 + np.log(0.95) * (t - 13))
    cours = pd.Series(10 * np.exp(log), index=jours)
    r = robustesse.rupture(cours)
    assert r["nette"] and r["date"].startswith(("2012", "2013"))
    assert r["pente_avant"] == pytest.approx(0.15, abs=0.01)
    s = robustesse.sensibilite(cours)
    assert s["statut"] == "alerte"
    assert robustesse.pente_glissante(cours)[-1]["pente"] < 0.05


def test_benefices_per_stable():
    jours = pd.bdate_range("2010-01-01", "2021-12-31")
    cours = pd.Series(np.exp(np.log(1.08) * (jours - jours[0]).days / 365.25) * 20, index=jours)
    moyennes = cours.groupby(cours.index.year).mean()
    comptes = [{"annee": int(a), "bpa": float(v) / 15} for a, v in moyennes.items()]
    b = benefices.analyser(cours, comptes)
    assert b["per_median"] == pytest.approx(15, rel=1e-6)
    assert b["droite_bpa"]["pente"] == pytest.approx(0.08, abs=0.005)
    assert abs(b["ecart_per_median"]) < 0.1
