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


def test_collage_tableur_annees_en_colonnes():
    """Forme habituelle d'un tableur : une ligne par poste, les annees en colonnes, tabulations."""
    texte = ("Poste\t2018\t2019\t2020\n"
             "Chiffre d'affaires\t1 200,5\t1 310\t1 290\n"
             "Bénéfice net (part du groupe)\t100\t110\t95\n"
             "BPA dilué\t2,10\t2,30\t1,99\n"
             "Ligne inconnue\t1\t2\t3\n")
    with TestClient(app) as client:
        vid = client.post("/valeurs", json={"symbole": "COLLE", "source": "import"}).json()["id"]
        r = client.post(f"/valeurs/{vid}/import/fondamentaux/texte", json={"texte": texte})
        assert r.status_code == 200, r.text
        lignes = {f["annee"]: f for f in client.get(f"/valeurs/{vid}/fondamentaux").json()}
        assert lignes[2018]["chiffre_affaires"] == 1200.5
        assert lignes[2019]["benefice_net"] == 110
        assert lignes[2020]["bpa"] == 1.99
        assert lignes[2020]["sources"]["bpa"] == "import"


def test_pdf_propose_puis_valide():
    from pathlib import Path
    pdf = (Path(__file__).parent / "donnees" / "rapport_exemple.pdf").read_bytes()
    with TestClient(app) as client:
        vid = client.post("/valeurs", json={"symbole": "PDF", "source": "import"}).json()["id"]
        proposition = client.post(f"/valeurs/{vid}/import/pdf", files={"fichier": ("r.pdf", pdf)}).json()
        assert proposition["multiplicateur"] == 1e6
        postes = {p["cle"]: p["valeurs"] for p in proposition["postes"]}
        assert postes["chiffre_affaires"] == {"2024": 27058.0, "2023": 27607.6}
        assert postes["bpa"] == {"2024": 5.72, "2023": 5.33}
        assert client.get(f"/valeurs/{vid}/fondamentaux").json() == []      # rien d'enregistre

        lot = {"annees": {"2024": {"chiffre_affaires": 27058e6, "bpa": 5.72, "charges_interets": -412.3e6}}}
        assert client.post(f"/valeurs/{vid}/import/lot", json=lot).status_code == 200
        ligne = client.get(f"/valeurs/{vid}/fondamentaux").json()[0]
        assert ligne["chiffre_affaires"] == 27058e6 and ligne["sources"]["bpa"] == "pdf"
        assert ligne["charges_interets"] == 412.3e6             # depense stockee en positif


def test_actualisation_en_tache_de_fond():
    import time
    with TestClient(app) as client:
        client.post("/valeurs", json={"symbole": "FOND1", "source": "import"})
        etat = client.post("/valeurs/actualiser").json()
        assert etat["total"] >= 1
        for _ in range(100):
            etat = client.get("/valeurs/actualisation").json()
            if not etat["en_cours"]:
                break
            time.sleep(0.1)
        assert not etat["en_cours"] and etat["faits"] == etat["total"]
        assert etat["fin"]


def test_indice_en_points(csv_cours):
    """Un indice se lit en points ; un ETF ou une action, dans sa devise."""
    with TestClient(app) as client:
        indice = client.post("/valeurs", json={"symbole": "IDXTEST", "source": "import", "type": "indice", "devise": "EUR"}).json()
        etf = client.post("/valeurs", json={"symbole": "ETFTEST", "source": "import", "type": "etf", "devise": "EUR"}).json()
        for v in (indice, etf):
            client.post(f"/valeurs/{v['id']}/import/cours", files={"fichier": ("c.csv", csv_cours)})
        assert client.get(f"/valeurs/{indice['id']}/analyse").json()["devise_affichee"] == "pts"
        assert client.get(f"/valeurs/{etf['id']}/analyse").json()["devise_affichee"] == "EUR"
