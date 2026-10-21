"""Assistant local : faux serveur Ollama (la CI n'a pas de modele), selection des pages, flux."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import assistant_service
from backend.sources import ollama

ACTUALITES = ("**SYNTHESE :** Actualité calme.\n**TON GENERAL :** plutôt positif\n- [positif] Contrat signé.\n"
              "A VERIFIER : montant du contrat")


class FauxOllama(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _repondre(self, corps: bytes, type_="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", type_)
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        self._repondre(json.dumps({"models": [{"name": "faux:1b", "size": 1, "details": {"parameter_size": "1B"}}]}).encode())

    def do_POST(self):
        demande = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if demande["stream"]:
            morceaux = [{"message": {"content": "La note "}}, {"message": {"content": "est bonne."}, "done": True}]
            self._repondre(b"\n".join(json.dumps(m).encode() for m in morceaux), "application/x-ndjson")
            return
        consigne = demande["messages"][-1]["content"]
        if "TON GENERAL" in consigne:
            texte = ACTUALITES
        elif "Une ligne par point" in consigne:    # lecture d'un lot, avec du bruit autour
            texte = "Voici les points :\n- [rupture] (p. 12) Cession de la branche historique annoncée.\nBonne lecture."
        else:                                      # resume ou questions
            texte = "- Quel poids pour la branche cédée ?"
        self._repondre(json.dumps({"message": {"content": texte}}).encode())


@pytest.fixture
def faux_ollama(monkeypatch):
    serveur = ThreadingHTTPServer(("127.0.0.1", 0), FauxOllama)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    monkeypatch.setattr(ollama, "ADRESSE", f"http://127.0.0.1:{serveur.server_port}")
    monkeypatch.setattr(ollama, "PLATEFORMES", ("linux", "win", "darwin"))
    yield
    serveur.shutdown()


def test_json_tolerant_et_adresse_locale(monkeypatch):
    assert ollama.json_tolerant('```json\n{"a": 1}\n```') == {"a": 1}
    assert ollama.json_tolerant('Voici : {"a": 2} voila') == {"a": 2}
    monkeypatch.setattr(ollama, "ADRESSE", "http://serveur-distant.example:11434")
    with pytest.raises(ollama.OllamaIndisponible, match="non locale"):
        ollama.modeles()


def test_choix_du_modele():
    assert ollama.choisir(["gemma4:e2b", "qwen3.5:9b"], None) == "qwen3.5:9b"
    assert ollama.choisir(["gemma4:e2b", "qwen3.5:9b"], "gemma4:e2b") == "gemma4:e2b"
    assert ollama.choisir(["inconnu:1b"], "absent") == "inconnu:1b"


def test_selection_des_pages():
    remplissage = " texte courant de rapport annuel " * 20
    pages = [
        "Sommaire\n" + "\n".join(f"Facteurs de risque .......... {i}" for i in range(30)),
        "Photo",
        "Chers actionnaires, " + remplissage,
        remplissage,
        "Facteurs de risque : risques de change, risques industriels. " + remplissage,
    ]
    assert assistant_service.selectionner(pages) == [3, 5]


def test_indisponible_sans_ollama(monkeypatch):
    monkeypatch.setattr(ollama, "ADRESSE", "http://127.0.0.1:9")      # rien n'ecoute
    monkeypatch.setattr(ollama, "PLATEFORMES", ("linux", "win", "darwin"))
    with TestClient(app) as client:
        assert client.get("/assistant").json()["disponible"] is False
        vid = client.post("/valeurs", json={"symbole": "IA0", "source": "import"}).json()["id"]
        assert client.post(f"/valeurs/{vid}/assistant/question", json={"question": "?"}).status_code == 409


def test_rapport_question_actualites(faux_ollama, monkeypatch, csv_cours):
    remplissage = " texte courant de rapport annuel " * 20
    pages = [remplissage] * 11 + ["Cession de la branche historique, restructuration. " + remplissage]
    monkeypatch.setattr(assistant_service, "pages_pdf", lambda contenu: pages)
    from backend.sources import actualites
    monkeypatch.setattr(actualites, "actualites", lambda nom, symbole, nombre=20: [
        {"titre": "Contrat signé", "lien": "https://exemple.fr", "source": "Presse", "moment": "2026-10-01T08:00:00"}])
    with TestClient(app) as client:
        etat = client.get("/assistant").json()
        assert etat["disponible"] and etat["modele"] == "faux:1b"
        vid = client.post("/valeurs", json={"symbole": "IA1", "source": "import", "nom": "IA SA"}).json()["id"]
        client.post(f"/valeurs/{vid}/import/cours", files={"fichier": ("c.csv", csv_cours)})

        travail = client.post(f"/valeurs/{vid}/assistant/rapport",
                              files={"fichier": ("rapport 2025.pdf", b"%PDF-1.4 faux", "application/pdf")}).json()["travail"]
        for _ in range(100):
            etat = client.get(f"/assistant/travaux/{travail}").json()
            if etat["termine"]:
                break
            time.sleep(0.05)
        assert etat["erreur"] is None, etat
        analyse = client.get(f"/valeurs/{vid}/assistant").json()[0]
        assert analyse["resultat"]["signaux_rupture"][0]["pages"] == [12] and analyse["resultat"]["pages_lues"] == [12]
        assert analyse["resultat"]["points"][0] == {"categorie": "rupture", "page": 12,
                                                    "texte": "Cession de la branche historique annoncée."}
        assert any(p["nom"] == "rapport 2025.pdf" for p in client.get(f"/valeurs/{vid}/journal/pieces").json())

        reponse = client.post(f"/valeurs/{vid}/assistant/question", json={"question": "La note ?", "historique": []})
        assert reponse.text == "La note est bonne."

        resume = client.post(f"/valeurs/{vid}/assistant/actualites").json()
        assert resume["ton_general"] == "plutôt positif"
        assert len(client.get(f"/valeurs/{vid}/assistant").json()) == 2
        client.delete(f"/valeurs/{vid}/assistant/{analyse['id']}")
        assert len(client.get(f"/valeurs/{vid}/assistant").json()) == 1


def test_contexte_compact(csv_cours):
    with TestClient(app) as client:
        vid = client.post("/valeurs", json={"symbole": "IA2", "source": "import", "nom": "Contexte"}).json()["id"]
        client.post(f"/valeurs/{vid}/import/cours", files={"fichier": ("c.csv", csv_cours)})
        from sqlmodel import Session

        from backend.db.db import engine
        with Session(engine) as db:
            contexte = assistant_service.contexte(db, vid)
        assert contexte["droite_de_regression"]["pente"] > 0.05
        assert len(json.dumps(contexte)) < 12000           # quelques milliers de jetons au plus


def test_lecture_tolerante_des_points():
    """Reponse en liste a puces (format JSON ignore), comme qwen3.5 sur un long extrait."""
    reponse = ("Voici les points :\n\n*   Activités en Russie déconsolidées depuis septembre 2022. (Page 74)\n"
               "- [rupture] (p. 75) Cession prévue de la branche historique.\n"
               "1. **Risque de change** hors zone euro (p. 80)\nFin.")
    points = assistant_service.lire_points(reponse)
    assert [(p["categorie"], p["page"]) for p in points] == [("risque", 74), ("rupture", 75), ("risque", 80)]
    assert points[2]["texte"] == "Risque de change hors zone euro."


def test_contexte_avec_comptes_complets(csv_cours):
    """Bilans complets (Altman, Beneish, multiples) : le cas qui manquait au premier essai reel."""
    from pathlib import Path
    comptes = json.loads((Path(__file__).parent / "donnees" / "reference_apple_sec.json").read_text())["comptes"]
    with TestClient(app) as client:
        vid = client.post("/valeurs", json={"symbole": "IA3", "source": "import", "nom": "Comptes"}).json()["id"]
        client.post(f"/valeurs/{vid}/import/cours", files={"fichier": ("c.csv", csv_cours)})
        for annee in comptes[-8:]:
            client.put(f"/valeurs/{vid}/fondamentaux/{annee['annee'] - 4}", json={k: v for k, v in annee.items() if k != "annee"})
        from sqlmodel import Session

        from backend.db.db import engine
        with Session(engine) as db:
            contexte = assistant_service.contexte(db, vid)
        assert contexte["qualite"]["altman"] is not None and contexte["qualite"]["piotroski"] is not None
        assert len(json.dumps(contexte)) < 12000
