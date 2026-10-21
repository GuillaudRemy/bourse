from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app

COMPOSITION = [{"symbole": "AAA.PA", "nom": "Société A", "secteur": "Industrie", "cik": None},
               {"symbole": "BBB.PA", "nom": "Société B", "secteur": "Luxe", "cik": None}]


def test_import_univers_et_listes():
    with TestClient(app) as client, patch("backend.sources.univers.composition", return_value=COMPOSITION), \
            patch("backend.services.taches.lancer", return_value={}):
        assert [m["valeur_id"] for m in client.get("/univers/cac40").json()] == [None, None]
        r = client.post("/univers/cac40/importer", json={"symboles": ["AAA.PA", "BBB.PA", "ZZZ.PA"], "liste": "CAC test"}).json()
        assert r["creees"] == 2
        assert all(m["valeur_id"] for m in client.get("/univers/cac40").json())
        liste = next(l for l in client.get("/listes").json() if l["nom"] == "CAC test")
        assert len(liste["valeur_ids"]) == 2
        client.delete(f"/listes/{liste['id']}/valeurs/{liste['valeur_ids'][0]}")
        assert len(next(l for l in client.get("/listes").json() if l["nom"] == "CAC test")["valeur_ids"]) == 1
        assert client.post("/listes", json={"nom": "CAC test"}).status_code == 409
