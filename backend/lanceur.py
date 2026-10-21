"""Lancement de la version de bureau : un double-clic, et l'application s'ouvre
dans le navigateur. La fenetre console doit rester ouverte ; la fermer arrete tout.

Au demarrage, la derniere version publiee sur GitHub est comparee a la version
installee ; si elle est plus recente, elle est telechargee, sa signature verifiee
(backend/mise_a_jour.py), puis installee. Sans internet, ou si GitHub ne repond pas,
l'application demarre simplement telle quelle.

Windows : la mise a jour passe par l'installateur, lance en silencieux.
Linux   : l'archive est extraite a cote, la nouvelle version est essayee sur une copie
          de la base, puis elle remplace le dossier du programme et on se relance.

Retour arriere : la base est copiee avant la premiere migration de la nouvelle version.
Si celle-ci ne demarre pas, la base est restauree et l'ancienne version reinstallee
(dossier conserve sous Linux, installateur conserve ou retelecharge sous Windows) ;
la version fautive n'est plus proposee.

Les donnees vivent hors du dossier du programme (%LOCALAPPDATA%\\Bourse sous Windows,
~/.local/share/bourse sous Linux) : une mise a jour ne touche jamais a la base.

Variables d'environnement utiles :
  BOURSE_DONNEES  dossier des donnees (base + sauvegardes)
  BOURSE_TEST=1   ni navigateur, ni mise a jour, ni valeurs d'exemple (tests automatiques)
  BOURSE_TEST_MAJ=1  avec BOURSE_TEST : autorise quand meme la mise a jour (test N-1 -> N)
  BOURSE_PORT     premier port essaye (8765 par defaut, puis les 19 suivants)

Usage : python -m backend.lanceur   (depuis la racine du paquet)
"""
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from backend import mise_a_jour as maj

RACINE = Path(__file__).resolve().parent.parent
ARCHIVES = {"nt": "Bourse-Setup.exe", "posix": "bourse-linux-x86_64.tar.gz"}
PORTS = range(int(os.environ.get("BOURSE_PORT", "8765")), int(os.environ.get("BOURSE_PORT", "8765")) + 20)
TEST = os.environ.get("BOURSE_TEST") == "1"
TEST_MAJ = os.environ.get("BOURSE_TEST_MAJ") == "1"


def _dossier_donnees() -> Path:
    if os.environ.get("BOURSE_DONNEES"):
        return Path(os.environ["BOURSE_DONNEES"])
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "Bourse"
    if _version_installee() != "dev":     # paquet Linux installe dans ~/.local/share/bourse/app
        return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "bourse"
    return RACINE                          # developpement : donnees/ a la racine du depot


def _version_installee() -> str:
    fichier = RACINE / "VERSION"
    return fichier.read_text().strip() if fichier.exists() else "dev"


def _base() -> Path:
    return _dossier_donnees() / "donnees" / "bourse.db"


# ── Etat d'une mise a jour en cours d'essai ──────────────────────────
def _fichier_etat() -> Path:
    return _dossier_donnees() / "mise_a_jour.json"


def _etat() -> dict:
    try:
        return json.loads(_fichier_etat().read_text())
    except (OSError, ValueError):
        return {}


def _ecrire_etat(etat: dict) -> None:
    _fichier_etat().parent.mkdir(parents=True, exist_ok=True)
    _fichier_etat().write_text(json.dumps(etat, indent=1))


def _copier_base(source: Path, cible: Path) -> None:
    """Copie coherente d'une base SQLite en mode WAL (une simple copie de fichier peut perdre des ecritures)."""
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.unlink(missing_ok=True)
    with sqlite3.connect(source) as origine, sqlite3.connect(cible) as copie:
        origine.backup(copie)


# ── Mise a jour ──────────────────────────────────────────────────────
def _mettre_a_jour() -> bool:
    """Vrai si une mise a jour a ete lancee : il faut alors quitter pour la laisser s'installer.
    Sous Linux, la mise a jour reussie relance directement la nouvelle version (exec)."""
    installee = _version_installee()
    if (TEST and not TEST_MAJ) or installee == "dev" or os.name not in ARCHIVES:
        return False
    nom = ARCHIVES[os.name]
    etat = _etat()
    try:
        publication = maj.chercher(installee, maj.canal_beta(_base()), set(etat.get("abandonnees", [])))
    except Exception as e:     # pas d'internet, GitHub indisponible…
        print(f"Verification des mises a jour impossible ({e}) : on continue avec la version {installee}.")
        return False
    if publication is None:
        return False

    print(f"Nouvelle version {publication.version} (installee : {installee}). Telechargement et verification…")
    try:
        fichier = maj.telecharger(publication, nom, Path(tempfile.gettempdir()))
    except maj.VerificationEchouee as e:
        print(f"Mise a jour {publication.version} refusee : {e}.")
        return False
    except Exception as e:
        print(f"Mise a jour impossible ({e}) : on continue avec la version {installee}.")
        return False

    etat.update({"de": installee, "vers": publication.version, "installateur": str(fichier)})
    try:
        if os.name == "nt":
            _ecrire_etat(etat)
            _installer_windows(fichier)
            return True
        _installer_linux(fichier, publication.version, etat)
    except Exception as e:
        print(f"Mise a jour impossible ({e}) : on continue avec la version {installee}.")
        _ecrire_etat({"abandonnees": etat.get("abandonnees", [])})
    return False


def _installer_windows(installateur: Path) -> None:
    print("Installation de la mise a jour : Bourse va se relancer tout seul dans un instant.")
    # Detache : l'installateur doit survivre a ce processus, qui quitte pour liberer ses fichiers.
    subprocess.Popen(
        [str(installateur), "/SILENT", "/SP-", "/NOCANCEL", "/NORESTART", "/SUPPRESSMSGBOXES"],
        # Constantes propres a Windows (absentes ailleurs, d'ou getattr).
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        close_fds=True,
    )


def _essayer(dossier: Path) -> None:
    """Demarre la version de `dossier` sur une COPIE des donnees ; leve une erreur si elle echoue."""
    with tempfile.TemporaryDirectory() as essai:
        if _base().exists():
            _copier_base(_base(), Path(essai) / "donnees" / "bourse.db")
        # Ports hors de la plage normale : un double-clic pendant l'essai ne doit pas ouvrir la copie.
        env = {**os.environ, "BOURSE_TEST": "1", "BOURSE_DONNEES": essai, "BOURSE_PORT": str(PORTS.stop + 50)}
        env.pop("BOURSE_TEST_MAJ", None)
        resultat = subprocess.run([str(dossier / "python" / "bin" / "python3"), "-m", "backend.lanceur", "--essai"],
                                  cwd=dossier, env=env, capture_output=True, text=True, timeout=300)
        if resultat.returncode != 0:
            raise RuntimeError("la nouvelle version ne demarre pas : " + (resultat.stderr or resultat.stdout)[-800:])


def _installer_linux(archive: Path, version: str, etat: dict) -> None:
    """Extrait a cote, essaie, puis echange les dossiers. L'ancien est garde jusqu'a ce que
    la nouvelle version ait demarre pour de bon (retour arriere)."""
    nouveau = RACINE.with_name(RACINE.name + ".nouveau")
    ancien = RACINE.with_name(RACINE.name + ".ancien")
    shutil.rmtree(nouveau, ignore_errors=True)
    shutil.rmtree(ancien, ignore_errors=True)
    extraction = Path(tempfile.mkdtemp(dir=RACINE.parent))
    with tarfile.open(archive) as t:
        t.extractall(extraction, filter="tar")
    (extraction / "bourse").rename(nouveau)
    shutil.rmtree(extraction)
    python = nouveau / "python" / "bin" / "python3"
    if (nouveau / "VERSION").read_text().strip() != version or not python.exists():
        shutil.rmtree(nouveau, ignore_errors=True)
        raise RuntimeError("archive incomplete")
    print("Essai de la nouvelle version sur une copie de vos donnees…")
    try:
        _essayer(nouveau)
    except Exception:
        shutil.rmtree(nouveau, ignore_errors=True)
        etat.setdefault("abandonnees", []).append(version)
        raise

    RACINE.rename(ancien)
    nouveau.rename(RACINE)
    archive.unlink(missing_ok=True)
    etat["installateur"] = None
    _ecrire_etat(etat)
    print(f"Bourse {version} installe. Redemarrage…")
    _relancer(RACINE)


def _relancer(dossier: Path) -> None:
    sys.stdout.flush()
    os.chdir(dossier)
    python = dossier / "python" / "bin" / "python3"
    os.execv(str(python), [str(python), "-m", "backend.lanceur"])


# ── Premier demarrage d'une nouvelle version : sauvegarde, confirmation, retour arriere ──
def _en_essai() -> dict | None:
    etat = _etat()
    if not etat.get("vers"):
        return None
    if etat["vers"] != _version_installee():     # etat perime (retour arriere deja fait, reinstallation…)
        _ecrire_etat({"abandonnees": etat.get("abandonnees", [])})
        return None
    return etat


def _sauvegarde_avant(etat: dict) -> Path:
    return _dossier_donnees() / "sauvegardes" / f"avant-mise-a-jour-{etat['vers']}.db"


def _confirmer(etat: dict) -> None:
    """La nouvelle version repond : on oublie l'ancienne."""
    shutil.rmtree(RACINE.with_name(RACINE.name + ".ancien"), ignore_errors=True)
    if os.name == "nt" and etat.get("installateur") and Path(etat["installateur"]).exists():
        # Garde l'installateur de cette version : il servira si la suivante ne demarre pas.
        versions = _dossier_donnees() / "versions"
        shutil.rmtree(versions, ignore_errors=True)
        versions.mkdir(parents=True)
        shutil.move(etat["installateur"], versions / f"Bourse-Setup-{etat['vers']}.exe")
    _ecrire_etat({"abandonnees": etat.get("abandonnees", [])})
    print(f"Mise a jour {etat['vers']} reussie.")


def _surveiller(adresse: str, etat: dict) -> None:
    for _ in range(240):
        try:
            urllib.request.urlopen(adresse + "/health", timeout=1)
            _confirmer(etat)
            return
        except OSError:
            time.sleep(0.5)


def _revenir(etat: dict, erreur: BaseException) -> None:
    """La nouvelle version ne demarre pas : base restauree, ancienne version reinstallee."""
    print(f"\nLa version {etat['vers']} ne demarre pas ({erreur}).")
    print(f"Retour a la version {etat['de']}…")
    sauvegarde = _sauvegarde_avant(etat)
    if sauvegarde.exists():
        for suffixe in ("", "-wal", "-shm"):
            Path(str(_base()) + suffixe).unlink(missing_ok=True)
        shutil.copy2(sauvegarde, _base())
    _ecrire_etat({"abandonnees": sorted(set(etat.get("abandonnees", [])) | {etat["vers"]})})

    if os.name == "nt":
        installateur = _dossier_donnees() / "versions" / f"Bourse-Setup-{etat['de']}.exe"
        if not installateur.exists():
            installateur = _retelecharger(etat["de"])
        _installer_windows(installateur)
        return
    ancien = RACINE.with_name(RACINE.name + ".ancien")
    if not ancien.exists():
        raise RuntimeError("ancienne version introuvable : reinstallez Bourse depuis GitHub") from erreur
    defaillant = RACINE.with_name(RACINE.name + ".defaillant")
    shutil.rmtree(defaillant, ignore_errors=True)
    RACINE.rename(defaillant)
    ancien.rename(RACINE)
    shutil.rmtree(defaillant, ignore_errors=True)
    _relancer(RACINE)


def _retelecharger(version: str) -> Path:
    """Installateur Windows d'une version precise, verifie s'il est signe (versions >= 0.5.0)."""
    donnees = json.loads(maj._lire(f"https://api.github.com/repos/{maj.DEPOT}/releases/tags/v{version}", 30))
    publication = maj.Publication(version, False, {a["name"]: a["browser_download_url"] for a in donnees["assets"]})
    if maj.SOMMES in publication.fichiers:
        return maj.telecharger(publication, ARCHIVES["nt"], Path(tempfile.gettempdir()))
    cible = Path(tempfile.gettempdir()) / f"bourse-{version}-{ARCHIVES['nt']}"
    with urllib.request.urlopen(publication.fichiers[ARCHIVES["nt"]], timeout=300) as r, open(cible, "wb") as f:
        shutil.copyfileobj(r, f)
    return cible


# ── Serveur ──────────────────────────────────────────────────────────
def _port_libre() -> int:
    for port in PORTS:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit(f"Aucun port libre entre {PORTS.start} et {PORTS.stop - 1}.")


def _deja_lance() -> str | None:
    """Si l'application tourne deja (double-clic de trop), on rouvre simplement le navigateur."""
    for port in PORTS:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.3) as r:
                if b'"ok"' in r.read():
                    return f"http://127.0.0.1:{port}"
        except OSError:
            continue
    return None


def _ouvrir_quand_pret(adresse: str) -> None:
    for _ in range(120):
        try:
            urllib.request.urlopen(adresse + "/health", timeout=1)
            webbrowser.open(adresse)
            return
        except OSError:
            time.sleep(0.5)


def _configurer_environnement() -> Path:
    """A fixer avant d'importer le backend : la configuration est lue a l'import."""
    donnees = _dossier_donnees()
    os.environ.setdefault("API_PREFIX", "/api")
    os.environ.setdefault("DOSSIER_FRONTEND", str(RACINE / "frontend" / "dist"))
    os.environ.setdefault("DB_NAME", str(donnees / "donnees" / "bourse.db"))
    os.environ.setdefault("DOSSIER_SAUVEGARDES", str(donnees / "sauvegardes"))
    if TEST:
        os.environ.setdefault("ACTUALISATION_AU_DEMARRAGE", "false")
        os.environ.setdefault("NOTIFICATIONS", "false")
    return donnees


def essai() -> None:
    """`--essai` : migre la base (une copie), demarre le serveur, verifie /health, s'arrete."""
    _configurer_environnement()
    from backend import migrate
    migrate.main()
    import uvicorn
    port = _port_libre()
    serveur = uvicorn.Server(uvicorn.Config("backend.main:app", host="127.0.0.1", port=port, log_level="warning"))
    fil = threading.Thread(target=serveur.run, daemon=True)
    fil.start()
    try:
        for _ in range(120):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as r:
                    if b'"ok"' in r.read():
                        print("essai reussi")
                        return
            except OSError:
                if not fil.is_alive():
                    break
                time.sleep(0.5)
        raise SystemExit("le serveur ne repond pas")
    finally:
        serveur.should_exit = True
        fil.join(timeout=10)


def main() -> None:
    # Une console Windows mal configuree ne doit jamais faire planter l'application sur un accent.
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(errors="replace")
    os.chdir(RACINE)
    if os.name == "nt":
        os.system("title Bourse")

    adresse = _deja_lance()
    if adresse:
        print(f"Bourse est deja ouvert : {adresse}")
        if not TEST:
            webbrowser.open(adresse)
        return

    etat = _en_essai()
    if etat is None and _mettre_a_jour():
        time.sleep(2)
        return
    try:
        demarrer(etat)
    except KeyboardInterrupt:
        raise
    except BaseException as e:
        if etat is None or etat.get("confirme"):
            raise
        _revenir(etat, e)


def demarrer(etat: dict | None) -> None:
    donnees = _configurer_environnement()
    if etat and _base().exists() and not _sauvegarde_avant(etat).exists():
        _copier_base(_base(), _sauvegarde_avant(etat))

    premiere_fois = not Path(os.environ["DB_NAME"]).exists()
    from backend import migrate
    migrate.main()
    if premiere_fois and not TEST:
        print("Premier lancement : ajout des valeurs d'exemple ; leurs données se téléchargent ensuite "
              "en arrière-plan (barre de progression dans l'application).")
        try:
            from backend import seed
            seed.main(actualiser=False)
        except Exception as e:   # pas d'internet : la base reste vide, ce n'est pas grave
            print(f"Valeurs d'exemple non ajoutees : {e}")

    import uvicorn
    port = _port_libre()
    adresse = f"http://127.0.0.1:{port}"
    print()
    print("=" * 60)
    print(f"  Bourse {_version_installee()} est ouvert dans votre navigateur :")
    print(f"  {adresse}")
    print("  Laissez cette fenetre ouverte pendant l'utilisation.")
    print("  Pour quitter : fermez cette fenetre.")
    print(f"  Donnees : {donnees}")
    print("=" * 60)
    if etat:
        def confirmer():
            _surveiller(adresse, etat)
            etat["confirme"] = True       # une erreur plus tard n'est plus un echec de la mise a jour
        threading.Thread(target=confirmer, daemon=True).start()
    if not TEST:
        threading.Thread(target=_ouvrir_quand_pret, args=(adresse,), daemon=True).start()
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    try:
        essai() if sys.argv[1:] == ["--essai"] else main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        # La fenetre se fermerait aussitot : on laisse le temps de lire l'erreur.
        print(f"\nErreur : {e}\n")
        if os.name == "nt" and not TEST:
            input("Appuyez sur Entree pour fermer…")
        raise
