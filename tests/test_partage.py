"""Partage entre PC par fichier : export, import sans doublon et sans ecraser les donnees locales."""
import json

from fastapi.testclient import TestClient

from backend.main import app


def _envoyer(client, chemin, contenu, **params):
    return client.post(chemin, params=params, files={"fichier": ("export.bourse.json", contenu, "application/json")})


def test_aller_retour_sans_doublon(csv_cours):
    with TestClient(app) as client:
        vid = client.post("/valeurs", json={"symbole": "PARTAGE", "source": "import", "nom": "Partage SA"}).json()["id"]
        client.post(f"/valeurs/{vid}/import/cours", files={"fichier": ("c.csv", csv_cours)})
        client.put(f"/valeurs/{vid}/journal/these", json={"pourquoi": "Leader"})
        decision = {"jour": "2024-03-01", "type": "achat", "prix": 10, "raison": "-1σ"}
        client.post(f"/valeurs/{vid}/journal/decisions", json=decision)
        client.post(f"/valeurs/{vid}/annotations", json={"type": "niveau", "donnees": {"prix": 12.5}})
        client.put(f"/valeurs/{vid}/fondamentaux/2024", json={"bpa": 5.0, "chiffre_affaires": 1e9})
        liste = client.post("/listes", json={"nom": "Partagée"}).json()
        client.post(f"/listes/{liste['id']}/valeurs", json={"valeur_ids": [vid]})
        compte = client.post("/portefeuille/comptes", json={"nom": "PEA partagé", "type": "PEA"}).json()
        client.post("/portefeuille/transactions", json={"compte_id": compte["id"], "valeur_id": vid, "jour": "2024-03-01",
                                                        "type": "achat", "quantite": 3, "prix": 10, "frais": 1})

        sans = client.get("/partage/export").json()
        assert "comptes" not in sans
        export = client.get("/partage/export", params={"portefeuille": True}).content
        donnees = json.loads(export)
        fiche = next(v for v in donnees["valeurs"] if v["symbole"] == "PARTAGE")
        assert fiche["these"]["pourquoi"] == "Leader" and len(fiche["cours"]) > 1000
        assert fiche["comptes_saisis"][0]["champs"]["bpa"] == 5.0

        # « Autre PC » : on efface tout, puis on importe.
        client.delete(f"/valeurs/{vid}")
        client.delete(f"/portefeuille/comptes/{compte['id']}")
        apercu = _envoyer(client, "/partage/apercu", export).json()
        assert "PARTAGE" in apercu["nouvelles_valeurs"] and apercu["transactions"] == 1
        bilan = _envoyer(client, "/partage/importer", export, portefeuille=True).json()
        assert bilan["valeurs"] >= 1 and bilan["theses"] >= 1 and bilan["transactions"] == 1
        nouvel_id = next(v["id"] for v in client.get("/valeurs").json() if v["symbole"] == "PARTAGE")
        assert client.get(f"/valeurs/{nouvel_id}/journal/these").json()["pourquoi"] == "Leader"
        assert client.get(f"/valeurs/{nouvel_id}/analyse").json()["regression"]["pente"] > 0.05
        assert nouvel_id in next(l for l in client.get("/listes").json() if l["nom"] == "Partagée")["valeur_ids"]

        # Saisie locale modifiee : l'import ne l'ecrase pas ; un second import ne double rien.
        client.put(f"/valeurs/{nouvel_id}/fondamentaux/2024", json={"bpa": 6.0})
        bilan = _envoyer(client, "/partage/importer", export, portefeuille=True).json()
        assert bilan == {k: 0 for k in bilan}
        bpa = next(f for f in client.get(f"/valeurs/{nouvel_id}/fondamentaux").json() if f["annee"] == 2024)["bpa"]
        assert bpa == 6.0
        assert len(client.get(f"/valeurs/{nouvel_id}/journal/decisions").json()) == 1
        assert len(client.get(f"/valeurs/{nouvel_id}/annotations").json()) == 1


def test_fichier_etranger_refuse():
    with TestClient(app) as client:
        assert _envoyer(client, "/partage/apercu", b"pas du json").status_code == 400
        assert _envoyer(client, "/partage/apercu", b'{"format": "autre"}').status_code == 400
