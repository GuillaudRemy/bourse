"""Test de mise a jour N-1 -> N de la version de bureau, sur une installation reelle.

    CLE_SIGNATURE=... python outils/test_mise_a_jour.py <dossier installe> <nouvelle archive ou installateur> <version N>

Le dossier installe doit contenir une version qui sait lire BOURSE_MAJ_API (>= 0.5.0). Sans
version precedente publiee compatible, on installe N puis on reecrit son fichier VERSION en
« 0.0.1 » : c'est alors le mecanisme de N lui-meme qui est teste.

Verifie, avec une publication locale (file://) signee par CLE_SIGNATURE :
  1. une publication mal signee est refusee : l'ancienne version demarre ;
  2. (Linux) une version qui ne demarre pas est abandonnee apres essai, l'ancienne demarre ;
  3. la vraie mise a jour s'installe, demarre, et les donnees sont intactes.
Bibliotheque standard + cryptography (pour signer).
"""
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from outils import signer  # noqa: E402

# Plage a part : une application Bourse deja ouverte sur ce PC ne doit pas fausser le test.
PORT = "8865"
PORTS = range(int(PORT), int(PORT) + 20)


def verifier(condition, message):
    print(("  ok    " if condition else "  ECHEC ") + message, flush=True)
    if not condition:
        for journal in sorted(Path(tempfile.gettempdir()).glob("bourse-maj-*/lancement-*.log")):
            print(f"--- {journal}\n{journal.read_text(encoding='utf-8', errors='replace')[-3000:]}")
        raise SystemExit(1)


def sante(delai=1.0):
    for port in PORTS:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=delai) as r:
                return port, json.load(r)
        except (OSError, ValueError):
            continue
    return None, None


def attendre_version(version: str | None, minutes=5):
    fin = time.time() + minutes * 60
    while time.time() < fin:
        port, infos = sante()
        if infos and (version is None or infos["version"] == version):
            return port
        time.sleep(1)
    return None


def appel(port, methode, chemin, donnees=None):
    corps = json.dumps(donnees).encode() if donnees is not None else None
    requete = urllib.request.Request(f"http://127.0.0.1:{port}{chemin}", data=corps, method=methode,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(requete, timeout=30) as r:
        return json.load(r)


def arreter(processus):
    if processus.poll() is None:
        processus.terminate()
        try:
            processus.wait(20)
        except subprocess.TimeoutExpired:
            processus.kill()
    for _ in range(30):              # le port doit etre libre pour l'etape suivante
        if sante(0.3)[0] is None:
            return
        time.sleep(1)


def publication(dossier: Path, fichier: Path, version: str, signature_valide=True) -> str:
    """Publication locale au format de l'API GitHub ; renvoie son adresse file://."""
    dossier.mkdir(parents=True, exist_ok=True)
    copie = dossier / fichier.name
    shutil.copy2(fichier, copie)
    signer.signer(dossier, [copie])
    if not signature_valide:          # signature d'un autre contenu
        sommes = (dossier / "SHA256SUMS").read_bytes()
        (dossier / "SHA256SUMS").write_bytes(sommes.replace(sommes[:8], b"00000000"))
    actifs = [{"name": f.name, "browser_download_url": f.as_uri()} for f in dossier.iterdir()]
    liste = dossier / "publications.json"
    liste.write_text(json.dumps([{"tag_name": f"v{version}", "prerelease": False, "draft": False, "assets": actifs}]))
    return liste.as_uri()


def lancer(installe: Path, donnees: Path, api: str | None):
    python = installe / "python" / ("python.exe" if os.name == "nt" else "bin/python3")
    env = {**os.environ, "BOURSE_TEST": "1", "BOURSE_DONNEES": str(donnees), "BOURSE_PORT": PORT}
    if api:
        env.update({"BOURSE_TEST_MAJ": "1", "BOURSE_MAJ_API": api})
    # Console a part (Windows) : l'installateur ferme l'ancienne version par un Ctrl+C envoye a SA console,
    # qui ne doit pas atteindre ce script. Sortie gardee dans un fichier, affichee en cas d'echec.
    journal = open(donnees.parent / f"lancement-{len(LANCES)}.log", "w", encoding="utf-8")  # noqa: SIM115
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000} if os.name == "nt" else {}  # sans fenetre
    processus = subprocess.Popen([str(python), "-u", "-m", "backend.lanceur"], cwd=installe, env=env,
                                 stdout=journal, stderr=subprocess.STDOUT, **options)
    LANCES.append(processus)
    return processus


def archive_defaillante(archive: Path, cible: Path, version: str) -> Path:
    """Meme paquet, mais le backend plante a l'import : l'essai doit echouer."""
    travail = Path(tempfile.mkdtemp(prefix="bourse-defaillant-"))
    with tarfile.open(archive) as t:
        t.extractall(travail, filter="tar")
    (travail / "bourse" / "VERSION").write_text(version + "\n")
    principal = travail / "bourse" / "backend" / "main.py"
    principal.write_text('raise RuntimeError("version defaillante (test)")\n' + principal.read_text())
    cible.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(cible, "w:gz") as t:
        t.add(travail / "bourse", arcname="bourse")
    shutil.rmtree(travail)
    return cible


LANCES: list = []


def main(installe: Path, nouvelle: Path, version: str) -> None:
    try:
        etapes(installe, nouvelle, version)
    finally:                          # jamais d'application orpheline, meme en cas d'echec
        for p in LANCES:
            arreter(p)


def etapes(installe: Path, nouvelle: Path, version: str) -> None:
    racine = Path(tempfile.mkdtemp(prefix="bourse-maj-"))
    donnees = racine / "donnees"
    ancienne = (installe / "VERSION").read_text().strip()
    print(f"Version installee : {ancienne} ; nouvelle : {version}")

    print("0. Donnees de depart")
    p = lancer(installe, donnees, None)
    port = attendre_version(ancienne, 2)
    verifier(port is not None, f"la version {ancienne} demarre")
    valeur = appel(port, "POST", "/api/valeurs", {"symbole": "MAJ", "source": "import", "nom": "Avant mise a jour"})
    arreter(p)

    print("1. Publication mal signee")
    p = lancer(installe, donnees, publication(racine / "refus", nouvelle, version, signature_valide=False))
    verifier(attendre_version(ancienne, 2) is not None, "refusee : l'ancienne version demarre")
    verifier((installe / "VERSION").read_text().strip() == ancienne, "rien n'a ete installe")
    arreter(p)

    if os.name != "nt":
        print("2. Version qui ne demarre pas")
        # Version defaillante juste sous la nouvelle (0.6.1 ou 0.6.1-beta.2 -> 0.6.1-beta.0) : un numero lisible,
        # sinon l'application l'ignore et l'essai n'a pas lieu.
        defaillante = "0.0.2" if ancienne == "0.0.1" else version.split("-")[0] + "-beta.0"
        archive = archive_defaillante(nouvelle, racine / "defaillante" / "src" / nouvelle.name, defaillante)
        p = lancer(installe, donnees, publication(racine / "defaillante" / "pub", archive, defaillante))
        verifier(attendre_version(ancienne, 5) is not None, "essai echoue : l'ancienne version demarre")
        etat = json.loads((donnees / "mise_a_jour.json").read_text())
        verifier(defaillante in etat.get("abandonnees", []), f"la version {defaillante} ne sera plus proposee")
        arreter(p)

    print("3. Mise a jour reelle")
    p = lancer(installe, donnees, publication(racine / "bonne", nouvelle, version))
    port = attendre_version(version, 8)
    verifier(port is not None, f"la version {version} demarre apres mise a jour")
    noms = [v["nom"] for v in appel(port, "GET", "/api/valeurs")]
    verifier(valeur["nom"] in noms, "les donnees sont intactes")
    verifier((donnees / "sauvegardes" / f"avant-mise-a-jour-{version}.db").exists(), "base sauvegardee avant migration")
    for _ in range(30):
        if not json.loads((donnees / "mise_a_jour.json").read_text()).get("vers"):
            break
        time.sleep(1)
    verifier(not json.loads((donnees / "mise_a_jour.json").read_text()).get("vers"), "mise a jour confirmee")
    if os.name != "nt":
        verifier(not installe.with_name(installe.name + ".ancien").exists(), "ancienne version supprimee apres confirmation")
    arreter(p)
    print("Test de mise a jour reussi.")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3].lstrip("v"))
