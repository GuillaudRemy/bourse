from fastapi.testclient import TestClient

from backend.main import app


def test_journal_complet():
    with TestClient(app) as client:
        vid = client.post("/valeurs", json={"symbole": "JOURNAL", "source": "import"}).json()["id"]
        vide = client.get(f"/valeurs/{vid}/journal/these").json()
        assert vide["pourquoi"] is None and len(vide["questions"]) >= 8

        q = vide["questions"][0]
        these = client.put(f"/valeurs/{vid}/journal/these", json={
            "pourquoi": " Leader mondial ", "prix_achat": 150, "checklist": {q: "oui"}}).json()
        assert these["pourquoi"] == "Leader mondial" and these["checklist"][q] == "oui"

        d = client.post(f"/valeurs/{vid}/journal/decisions",
                        json={"jour": "2024-03-01", "type": "achat", "prix": 148.5, "raison": "Sous -1σ"}).json()
        client.put(f"/valeurs/{vid}/journal/decisions/{d['id']}",
                   json={**d, "relecture": "Bon point d'entrée", "verdict": "bonne"})
        assert client.get(f"/valeurs/{vid}/journal/decisions").json()[0]["verdict"] == "bonne"
        assert client.post(f"/valeurs/{vid}/journal/decisions", json={"jour": "2024-03-01", "type": "pari"}).status_code == 422

        piece = client.post(f"/valeurs/{vid}/journal/pieces",
                            files={"fichier": ("rapport annuel.pdf", b"%PDF-1.4 test", "application/pdf")}).json()
        assert client.get(f"/valeurs/{vid}/journal/pieces/{piece['id']}").content == b"%PDF-1.4 test"
        assert client.delete(f"/valeurs/{vid}/journal/pieces/{piece['id']}").status_code == 204
        assert client.get(f"/valeurs/{vid}/journal/pieces").json() == []
