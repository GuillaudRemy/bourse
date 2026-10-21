"""Portefeuille : PRU, plus-values, TWR, XIRR, fiscalite, import de releve."""
from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.analyse import portefeuille as pf
from backend.main import app


def test_pru_et_plus_values():
    t = [
        {"id": 1, "jour": date(2020, 1, 2), "type": "achat", "valeur_id": 7, "quantite": 10, "frais": 5, "montant": -1005},
        {"id": 2, "jour": date(2021, 1, 4), "type": "achat", "valeur_id": 7, "quantite": 10, "frais": 5, "montant": -2005},
        {"id": 3, "jour": date(2022, 1, 3), "type": "vente", "valeur_id": 7, "quantite": 5, "frais": 5, "montant": 995},
        {"id": 4, "jour": date(2022, 6, 1), "type": "dividende", "valeur_id": 7, "montant": 30},
    ]
    ligne = pf.positions(t)[7]
    assert ligne.quantite == 15
    assert ligne.pru == pytest.approx(3010 / 20)                 # frais compris
    assert ligne.plus_value_realisee == pytest.approx(995 - 5 * 3010 / 20)
    assert ligne.dividendes == 30


def test_twr_neutralise_les_apports_et_xirr():
    jours = pd.bdate_range("2020-01-01", periods=500)
    prix = pd.Series(100 * 1.0004 ** np.arange(500), index=jours)       # +0,04 % par seance
    t = [{"id": 1, "jour": jours[0].date(), "type": "achat", "valeur_id": 1, "quantite": 10, "montant": -1000.0},
         {"id": 2, "jour": jours[250].date(), "type": "achat", "valeur_id": 1, "quantite": 100,
          "montant": -float(prix.iloc[250]) * 100}]
    quotidien = pf.valeur_quotidienne(t, {1: prix})
    quotidien = quotidien[quotidien.index <= jours[-1]]
    # Le TWR suit le prix, quel que soit le gros apport en cours de route.
    assert pf.twr(quotidien).iloc[-1] == pytest.approx(prix.iloc[-1] / prix.iloc[0] - 1, rel=1e-6)
    taux = pf.xirr(pf.flux_investisseur(quotidien))
    assert taux == pytest.approx(1.0004 ** (365.25 * 500 / (jours[-1] - jours[0]).days) - 1, abs=0.01)


def test_parcours_portefeuille_et_fiscalite(csv_cours):
    with TestClient(app) as client:
        vid = client.post("/valeurs", json={"symbole": "PFTEST", "source": "import", "nom": "Test"}).json()["id"]
        client.post(f"/valeurs/{vid}/import/cours", files={"fichier": ("c.csv", csv_cours)})
        cto = client.post("/portefeuille/comptes", json={"nom": "Compte-titres", "type": "CTO"}).json()["id"]
        r = client.post("/portefeuille/transactions", json={
            "compte_id": cto, "valeur_id": vid, "jour": "2015-03-02", "type": "achat", "quantite": 10, "prix": 100, "frais": 2})
        assert r.status_code == 201 and r.json()["montant"] == -1002
        client.post("/portefeuille/transactions", json={
            "compte_id": cto, "valeur_id": vid, "jour": "2018-03-01", "type": "vente", "quantite": 4, "prix": 150, "frais": 2})
        client.post("/portefeuille/transactions", json={
            "compte_id": cto, "valeur_id": vid, "jour": "2018-06-01", "type": "dividende", "montant": 12})
        assert client.post("/portefeuille/transactions", json={
            "compte_id": cto, "jour": "2018-06-01", "type": "achat", "quantite": 1, "prix": 1}).status_code == 422

        s = client.get("/portefeuille", params={"compte_id": cto}).json()
        position = s["positions"][0]
        assert position["quantite"] == 6 and position["pru"] == pytest.approx(100.2)
        assert position["plus_value_realisee"] == pytest.approx(598 - 4 * 100.2)
        annee = s["fiscalite"]["comptes"][0]["annees"][0]
        assert annee["annee"] == 2018 and annee["impot_pfu"] == pytest.approx(0.30 * (598 - 400.8 + 12))
        assert s["performance"]["xirr"] is not None


def test_releve_degiro_quantite_signee():
    releve = ("Date,Heure,Produit,Code ISIN,Quantité,Cours,Frais de courtage,Montant\n"
              "02-03-2021,09:01,TEST SA,FR0000000001,10,100,\"2,00\",-1002\n"
              "05-04-2022,10:00,TEST SA,FR0000000001,-4,150,\"2,00\",598\n").encode()
    with TestClient(app) as client:
        client.post("/valeurs", json={"symbole": "RELEVE", "source": "import"})
        client.patch("/valeurs/" + str(next(v["id"] for v in client.get("/valeurs").json() if v["symbole"] == "RELEVE")),
                     json={"isin": "FR0000000001"})
        compte = client.post("/portefeuille/comptes", json={"nom": "Degiro", "type": "CTO"}).json()["id"]
        proposition = client.post(f"/portefeuille/comptes/{compte}/releve", files={"fichier": ("r.csv", releve)}).json()
        types = [l["type"] for l in proposition["lignes"]]
        assert types == ["achat", "vente"] and all(l["valeur_id"] for l in proposition["lignes"])
        assert proposition["lignes"][1]["quantite"] == 4
        r = client.post(f"/portefeuille/comptes/{compte}/releve/valider", json={"lignes": proposition["lignes"]}).json()
        assert r["crees"] == 2


def test_divisions_ramenees_a_la_base_actuelle():
    """30 actions achetees avant une division par 4 = 120 actions aujourd'hui ; les cours
    historiques (ajustes) valent le quart : la valeur du portefeuille ne doit pas s'effondrer."""
    jours = pd.bdate_range("2020-01-01", periods=300)
    prix = pd.Series(40.0, index=jours)                       # cours ajuste : 160 / 4
    divisions = {1: [(jours[200].date(), 4.0)]}
    t = [{"id": 1, "jour": jours[10].date(), "type": "achat", "valeur_id": 1, "quantite": 30, "montant": -30 * 160.0}]
    ligne = pf.positions(t, divisions)[1]
    assert ligne.quantite == 120 and ligne.pru == pytest.approx(40)
    quotidien = pf.valeur_quotidienne(t, {1: prix}, divisions)
    assert quotidien["valeur"].iloc[-1] == pytest.approx(4800)
    assert abs(pf.twr(quotidien[quotidien.index <= jours[-1]]).iloc[-1]) < 1e-9


def test_fiscalite_taux_par_annee_et_report_des_moins_values():
    from backend.analyse import fiscalite as f
    assert f.pfu(2025) == pytest.approx(0.30) and f.pfu(2026) == pytest.approx(0.314)
    ventes = [(date(2024, 5, 1), -1000.0), (date(2026, 3, 1), 1500.0), (date(2026, 9, 1), 200.0)]
    lignes = {l["annee"]: l for l in f.compte_titres(ventes, {2026: 100.0}, tmi=0.11)}
    assert lignes[2024]["impot_pfu"] == 0 and lignes[2024]["report_disponible"] == 1000
    # 2026 : 1 700 de plus-values - 1 000 de moins-values reportees = 700, + 100 de dividendes, a 31,4 %.
    assert lignes[2026]["moins_values_anterieures_imputees"] == 1000
    assert lignes[2026]["impot_pfu"] == pytest.approx(0.314 * 800)
    assert lignes[2026]["impot_bareme"] == pytest.approx(0.11 * (700 + 60) + 0.186 * 800)
    # Moins-value trop ancienne (plus de 10 ans) : perdue.
    vieilles = {l["annee"]: l for l in f.compte_titres([(date(2010, 1, 1), -500.0), (date(2021, 1, 1), 500.0)], {})}
    assert vieilles[2021]["moins_values_anterieures_imputees"] == 0
    p = f.pea(versements=10000, valeur=16000, anciennete=6, type_="PEA", annee=2026)
    assert p["impot_retrait"] == pytest.approx(0.186 * 6000) and p["reste"] == 140000
    assert f.pea(10000, 16000, 3, "PEA", 2026)["impot_retrait"] == pytest.approx(0.314 * 6000)


def test_frais_courtier_et_ttf():
    from backend.analyse import frais as f
    assert f.taux_ttf(date(2025, 4, 1)) == 0.004 and f.taux_ttf(date(2024, 6, 1)) == 0.003
    assert f.taux_ttf(date(2015, 1, 1)) == 0.002 and f.taux_ttf(date(2010, 1, 1)) == 0
    assert f.assujetti_ttf("action", "France", 5e9) and not f.assujetti_ttf("etf", "France", 5e9)
    assert not f.assujetti_ttf("action", "Netherlands", 5e10)            # Airbus : siege aux Pays-Bas
    # 1 € + 0,1 % sur 2 000 € = 3 € ; TTF 0,4 % = 8 € a l'achat seulement.
    achat = f.ordre(2000, "achat", date(2026, 1, 5), {"fixe": 1, "pct": 0.001, "min": 0}, True)
    assert achat == {"courtage": 3.0, "ttf": 8.0, "total": 11.0, "taux_ttf": 0.004}
    assert f.ordre(2000, "vente", date(2026, 1, 5), {"fixe": 1, "pct": 0.001}, True)["ttf"] == 0
    assert f.courtage(100, fixe=0, pct=0.001, minimum=2.5) == 2.5


def test_frais_calcules_si_non_saisis():
    with TestClient(app) as client:
        vid = client.post("/valeurs", json={"symbole": "FRAIS", "source": "import", "devise": "EUR"}).json()["id"]
        compte = client.post("/portefeuille/comptes", json={"nom": "Courtier X", "type": "CTO",
                                                            "frais_fixe": 1, "frais_pct": 0.001}).json()["id"]
        t = client.post("/portefeuille/transactions", json={"compte_id": compte, "valeur_id": vid, "jour": "2026-01-05",
                                                            "type": "achat", "quantite": 20, "prix": 100}).json()
        assert t["frais"] == 3.0 and t["ttf"] == 0 and t["montant"] == -2003.0     # valeur sans pays : pas de TTF
        apercu = client.get("/portefeuille/frais", params={"compte_id": compte, "type": "achat", "quantite": 20,
                                                           "prix": 100, "jour": "2026-01-05", "valeur_id": vid}).json()
        assert apercu["courtage"] == 3.0 and apercu["ttf_applicable"] is False


def test_correlations_sans_cours():
    """Positions dont les cours ne sont pas encore telecharges : pas de plantage."""
    import pandas as pd

    from backend.analyse import portefeuille as pf
    vide = pd.Series(dtype=float)
    assert pf.correlations({1: vide, 2: vide}) == {}
    jours = pd.bdate_range("2023-01-02", periods=900)
    serie = pd.Series(range(1, 901), index=jours, dtype=float)
    assert pf.correlations({1: serie, 2: serie * 2, 3: vide})["ids"] == [1, 2]
