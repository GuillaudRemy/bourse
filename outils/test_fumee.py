"""Test de fumee de la version de bureau : lance l'application comme un utilisateur
(son propre Python, son propre dossier), puis verifie qu'elle repond et calcule.

    python outils/test_fumee.py <dossier de l'application>

Sans dependance : bibliotheque standard seulement. La partie Yahoo est indicative
(les serveurs d'integration continue sont parfois limites par Yahoo) : elle
avertit sans faire echouer le test.
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

PORT = 8765


def appel(methode, chemin, corps=None, entetes=None, delai=60):
    requete = urllib.request.Request(f"http://127.0.0.1:{PORT}{chemin}", data=corps, method=methode,
                                     headers=entetes or {})
    try:
        with urllib.request.urlopen(requete, timeout=delai) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def json_(methode, chemin, donnees=None):
    corps = json.dumps(donnees).encode() if donnees is not None else None
    statut, contenu = appel(methode, chemin, corps, {"Content-Type": "application/json"})
    return statut, json.loads(contenu) if contenu else None


def envoyer_fichier(chemin, nom, contenu: bytes):
    limite = uuid.uuid4().hex
    corps = (f"--{limite}\r\nContent-Disposition: form-data; name=\"fichier\"; filename=\"{nom}\"\r\n"
             f"Content-Type: text/csv\r\n\r\n").encode() + contenu + f"\r\n--{limite}--\r\n".encode()
    statut, reponse = appel("POST", chemin, corps, {"Content-Type": f"multipart/form-data; boundary={limite}"})
    return statut, json.loads(reponse)


def cours_csv() -> bytes:
    """20 ans de cours a +8 %/an avec une oscillation, au format francais."""
    lignes, t0 = ["Date;Clôture"], time.mktime((2005, 1, 3, 0, 0, 0, 0, 0, -1))
    for i in range(0, 20 * 365):
        jour = time.localtime(t0 + i * 86400)
        if jour.tm_wday < 5:
            valeur = 30 * 1.08 ** (i / 365) * math.exp(0.15 * math.sin(i / 200))
            lignes.append(f"{time.strftime('%d/%m/%Y', jour)};{valeur:.3f}".replace(".", ","))
    return "\n".join(lignes).encode()


def verifier(condition, message):
    print(("  ok    " if condition else "  ECHEC ") + message)
    if not condition:
        raise SystemExit(1)


def main(dossier: Path) -> None:
    python = dossier / "python" / ("python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        python = Path(sys.executable)
    donnees = Path(tempfile.mkdtemp(prefix="bourse-fumee-"))
    env = {**os.environ, "BOURSE_TEST": "1", "BOURSE_DONNEES": str(donnees)}
    print(f"Lancement : {python} -m backend.lanceur (dans {dossier})")
    processus = subprocess.Popen([str(python), "-m", "backend.lanceur"], cwd=dossier, env=env)
    try:
        for _ in range(120):
            try:
                if appel("GET", "/health", delai=2)[0] == 200:
                    break
            except OSError:
                time.sleep(1)
        else:
            verifier(False, "l'application demarre en moins de 2 minutes")

        statut, sante = json_("GET", "/health")
        verifier(statut == 200, f"l'application repond (version {sante['version']})")
        statut, page = appel("GET", "/valeurs/1")
        verifier(statut == 200 and b'id="root"' in page, "l'interface est servie")
        statut, _ = appel("GET", "/assets/inexistant.js")
        verifier(statut == 200, "les adresses inconnues renvoient l'interface")

        statut, valeur = json_("POST", "/api/valeurs", {"symbole": "FUMEE", "source": "import", "nom": "Fumée"})
        verifier(statut == 201, "creation d'une valeur importee")
        statut, resultat = envoyer_fichier(f"/api/valeurs/{valeur['id']}/import/cours", "cours.csv", cours_csv())
        verifier(statut == 200, f"import CSV : {resultat.get('message', resultat)}")
        statut, analyse = json_("GET", f"/api/valeurs/{valeur['id']}/analyse")
        pente = analyse["regression"]["pente"]
        verifier(statut == 200 and abs(pente - 0.08) < 0.02, f"analyse : pente {pente:.1%} (attendu ≈ 8 %)")
        verifier(analyse["stats"]["rsi"] is not None, "indicateurs techniques calcules")
        verifier((donnees / "donnees" / "bourse.db").exists(), "base creee dans le dossier de donnees")

        statut, yahoo = json_("POST", "/api/valeurs", {"symbole": "AI.PA"})
        if statut == 201:
            statut, analyse = json_("GET", f"/api/valeurs/{yahoo['id']}/analyse")
            print(f"  ok    Yahoo Finance : Air Liquide, pente {analyse['regression']['pente']:.1%}")
        else:
            print(f"  AVERTISSEMENT Yahoo Finance injoignable depuis cette machine ({statut}) : {yahoo}")
        print("Test de fumee reussi.")
    finally:
        processus.terminate()
        processus.wait(timeout=20)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd())
