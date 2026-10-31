"""Alertes (declenchement sur transition), calendrier, resume du jour."""
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.api import suivi
from backend.db.db import engine
from backend.db.schema import Declenchement, Evenement, Valeur
from backend.main import app


def test_alertes_se_declenchent_une_fois(csv_cours):
    with TestClient(app) as client:
        vid = client.post("/valeurs", json={"symbole": "ALERTE", "source": "import"}).json()["id"]
        # Valeur importee : les alertes par defaut (couloir ±2σ) sont creees aussi.
        assert {a["type"] for a in client.get("/alertes", params={"valeur_id": vid}).json()["alertes"]} == \
            {"sigma_sous", "sigma_dessus"}
        client.post(f"/valeurs/{vid}/import/cours", files={"fichier": ("c.csv", csv_cours)})
        avant = client.get("/alertes/declenchements").json()["non_lus"]
        alerte = client.post("/alertes", json={"valeur_id": vid, "type": "cours_dessus", "seuil": 0.01}).json()
        assert alerte["derniere"] is not None                     # vraie tout de suite : declenchee
        apres = client.get("/alertes/declenchements").json()
        assert apres["non_lus"] == avant + 1 and "Cours ≥ 0,01" in apres["liste"][0]["message"]

        # Reevaluer sans changement : pas de nouveau declenchement.
        client.post(f"/valeurs/{vid}/actualiser")
        assert client.get("/alertes/declenchements").json()["non_lus"] == avant + 1
        client.post("/alertes/lues")
        assert client.get("/alertes/declenchements").json()["non_lus"] == 0
        assert client.post("/alertes", json={"valeur_id": vid, "type": "cours_dessus"}).status_code == 422


def test_resume_et_calendrier():
    with TestClient(app) as client:
        r = client.get("/resume").json()
        assert {"hausses", "baisses", "sous_droite", "dessus_droite", "evenements", "alertes", "portefeuille"} <= set(r)
        assert isinstance(client.get("/calendrier").json(), list)


def test_aujourdhui_ne_parle_que_d_actions(monkeypatch):
    def ligne(i, type_, position, variation):
        return {"valeur": {"id": i, "nom": f"{type_} {i}", "type": type_, "devise": "EUR"}, "qualite": "ok",
                "position": position, "variation_jour": variation, "zone": "neutre", "dernier": 10.0}
    # 7 actions de -3σ a +3σ, un ETF plus extreme que toutes.
    lignes = [ligne(100 + i, "action", i - 3.0, (i - 3.0) / 100) for i in range(7)] + [ligne(99, "etf", -9.0, -0.5)]
    monkeypatch.setattr(suivi.AnalyseService, "synthese", lambda self: lignes)
    with TestClient(app) as client:
        with Session(engine) as db:
            action = Valeur(symbole="AUJ.ACT", nom="Action du jour")
            etf = Valeur(symbole="AUJ.ETF", nom="ETF du jour", type="etf")
            db.add_all([action, etf])
            db.flush()
            for i in range(12):
                db.add(Evenement(valeur_id=action.id, jour=date.today() + timedelta(days=i * 10), type="resultats"))
            db.add(Evenement(valeur_id=etf.id, jour=date.today(), type="detachement"))
            db.add(Evenement(valeur_id=action.id, jour=date.today() - timedelta(days=1), type="resultats"))
            for i in range(7):
                db.add(Declenchement(valeur_id=action.id, message=f"action {i}"))
            db.add(Declenchement(valeur_id=etf.id, message="etf"))
            db.commit()
            ids = [action.id, etf.id]
        r = client.get("/resume").json()
        try:
            assert r["nombre_actions"] == 7
            assert [l["position"] for l in r["sous_droite"]] == [-3.0, -2.0, -1.0]   # jamais du bon cote de la droite
            assert [l["position"] for l in r["dessus_droite"]] == [3.0, 2.0, 1.0]
            assert [l["id"] for l in r["hausses"]] == [106, 105, 104]
            assert [l["id"] for l in r["baisses"]] == [100, 101, 102]
            assert len(r["evenements"]) == 10 and r["evenements"][0]["nom"] == "Action du jour"
            assert r["evenements"] == sorted(r["evenements"], key=lambda e: e["jour"])
            assert r["evenements_14_jours"] == 2
            assert len(r["alertes"]["liste"]) == 5 and r["alertes"]["non_lus"] >= 7
            assert all(a["valeur_id"] == ids[0] for a in r["alertes"]["liste"])
        finally:
            for i in ids:
                client.delete(f"/valeurs/{i}")
