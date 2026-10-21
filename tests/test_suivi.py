"""Alertes (declenchement sur transition), calendrier, resume du jour."""
from fastapi.testclient import TestClient

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
        assert {"hausses", "baisses", "opportunites", "evenements", "alertes", "portefeuille"} <= set(r)
        assert isinstance(client.get("/calendrier").json(), list)
