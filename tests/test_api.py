"""Parcours complet par l'API, sans internet : valeur importee, cours CSV, analyse, fondamentaux."""
from fastapi.testclient import TestClient
from backend.main import app


def test_parcours_complet(csv_cours):
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"

        valeur = client.post("/valeurs", json={"symbole": "test", "source": "import", "nom": "Test"}).json()
        vid = valeur["id"]
        assert valeur["symbole"] == "TEST"
        assert client.post("/valeurs", json={"symbole": "TEST", "source": "import"}).status_code == 409

        r = client.post(f"/valeurs/{vid}/import/cours", files={"fichier": ("cours.csv", csv_cours)})
        assert r.status_code == 200, r.text
        assert r.json()["cours"] > 6000

        r = client.post(f"/valeurs/{vid}/import/fondamentaux", files={
            "fichier": ("f.csv", "Année;BPA;Bénéfice net\n2015;2,5;1 200M\n2020;3,9;1,9Md\n".encode()),
        })
        assert r.status_code == 200, r.text
        assert client.put(f"/valeurs/{vid}/fondamentaux/2024", json={"bpa": 5.1}).json()["source"] == "manuel"

        analyse = client.get(f"/valeurs/{vid}/analyse").json()
        assert abs(analyse["regression"]["pente"] - 0.10) < 0.02
        assert analyse["base_ajustee"] is False          # pas de colonne ajustee dans le CSV
        assert len(analyse["fiabilite"]["verifications"]) == 3
        assert len(analyse["series"]["jours"]) == len(analyse["indicateurs"]["rsi"])

        ligne = next(l for l in client.get("/valeurs/synthese").json() if l["valeur"]["id"] == vid)
        assert ligne["zone"]

        mauvais = client.post(f"/valeurs/{vid}/import/cours", files={"fichier": ("x.csv", b"a,b\n1,2")})
        assert mauvais.status_code == 400

        assert client.delete(f"/valeurs/{vid}").status_code == 204
        assert client.get(f"/valeurs/{vid}").status_code == 404
