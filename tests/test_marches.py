"""Version 0.6.0 : devises, taux, obligations, cryptomonnaies ; taux sans risque ; historique du consensus."""
from datetime import date, timedelta

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.db.db import engine
from backend.main import app
from backend.services import consensus_service, taux_service
from backend.sources import bce, catalogue


def _taux_fictifs(cle, debut=None):
    """Un taux qui passe sous zero (comme le Bund en 2016-2021) puis remonte a 3 %."""
    jours = pd.bdate_range("2012-01-02", "2026-10-28")
    valeurs = np.concatenate([np.linspace(2.0, -0.6, len(jours) // 2), np.linspace(-0.6, 3.0, len(jours) - len(jours) // 2)])
    return pd.DataFrame({"jour": [j.date() for j in jours], "ouverture": valeurs, "haut": valeurs, "bas": valeurs,
                         "cloture": valeurs, "ajuste": valeurs, "volume": None})


def test_catalogue_coherent():
    symboles = [e.symbole for entrees in catalogue.FAMILLES.values() for e in entrees]
    assert len(symboles) == len(set(symboles))
    assert all(e.serie for e in catalogue.TAUX if e.source == "bce")
    assert set(catalogue.AVERTISSEMENTS) == set(catalogue.FAMILLES)
    assert catalogue.nom("gc=f") == "Or (once troy)" and catalogue.nom("^TNX") == "Taux américain à 10 ans"


def test_taux_bce_sans_droite_variations_en_points(monkeypatch):
    monkeypatch.setattr(bce, "serie", _taux_fictifs)
    with TestClient(app) as client:
        v = client.post("/valeurs", json={"symbole": "TAUX-DE-10A"}).json()
        assert (v["type"], v["source"], v["devise"]) == ("taux", "bce", None)
        assert v["nom"] == "Bund 10 ans (Allemagne)"
        a = client.get(f"/valeurs/{v['id']}/analyse").json()
        assert a["regression"] is None and a["sans_droite"] and a["devise_affichee"] == "%"
        assert "négatif" in a["avertissement_indice"]["texte"]
        assert a["stats"]["en_points"] and abs(a["stats"]["variation_jour"]) < 0.1     # en points, pas en %
        ligne = next(x for x in client.get("/valeurs/synthese").json() if x["valeur"]["id"] == v["id"])
        assert ligne["en_points"] and ligne.get("position") is None and ligne["capitalisation_eur"] is None
        assert a["qualite"]["statut"] == "ok"               # taux negatifs : normaux, pas une anomalie
        assert client.get(f"/backtest/{v['id']}").status_code == 409
        # Actualisation rapide : le dernier mois seulement.
        appels = []
        monkeypatch.setattr(bce, "serie", lambda cle, debut=None: appels.append(debut) or _taux_fictifs(cle).tail(5))
        client.post(f"/valeurs/{v['id']}/actualiser")
        assert appels == [None]                              # bouton de la fiche : toute la serie


def test_catalogue_api():
    with TestClient(app) as client:
        c = client.get("/valeurs/catalogue").json()
        assert set(c) == {"matiere", "devise", "taux", "obligation", "crypto"}
        assert any(e["symbole"] == "TAUX-FR-10A" and e["source"] == "bce" for e in c["taux"])


def test_actualisation_par_defaut_du_dcf(monkeypatch):
    monkeypatch.setattr(taux_service, "prime", lambda: 0.05)
    assert taux_service.actualisation_par_defaut(None) is None
    assert taux_service.actualisation_par_defaut({"taux": 0.0339}) == 0.085
    assert taux_service.actualisation_par_defaut({"taux": -0.005}) == 0.06      # borne basse (taux negatifs de 2020)
    assert taux_service.actualisation_par_defaut({"taux": 0.12}) == 0.15
    assert taux_service.zone("USD") == "USD" and taux_service.zone("GBp") == "EUR"


def test_historique_du_consensus():
    with TestClient(app) as client:
        v = client.post("/valeurs", json={"symbole": "CONS1", "source": "import"}).json()
    donnees = {"exercices": [{"decalage": 0, "bpa": 5.0, "analystes": 12}, {"decalage": 1, "bpa": 5.6}],
               "objectif": {"mean": 120.0}}
    with Session(engine) as db:
        consensus_service.enregistrer(db, v["id"], donnees)
        donnees["exercices"][0]["bpa"] = 4.8                       # revision dans la journee : on garde la derniere
        consensus_service.enregistrer(db, v["id"], donnees)
        h = consensus_service.historique(db, v["id"])
    assert len(h) == 2 and h[0]["bpa"] == 4.8 and h[0]["annee"] == date.today().year and h[1]["annee"] == date.today().year + 1
    assert h[0]["objectif"] == 120.0 and h[0]["analystes"] == 12


def test_serie_bce_mensuelle_datee_en_fin_de_mois(monkeypatch):
    class Reponse:
        text = "TIME_PERIOD,OBS_VALUE\n2026-08,4\n2026-09,4.44\n"
    monkeypatch.setattr(bce, "obtenir", lambda *a, **k: Reponse())
    df = bce.serie("IRS/M.FR.L.L40.CI.0000.EUR.N.Z", date.today() - timedelta(days=60))
    assert list(df["jour"]) == [date(2026, 8, 31), date(2026, 9, 30)] and list(df["cloture"]) == [4.0, 4.44]
