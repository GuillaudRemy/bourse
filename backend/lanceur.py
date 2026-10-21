"""Lancement de la version de bureau : un double-clic, et l'application s'ouvre
dans le navigateur. La fenetre console doit rester ouverte ; la fermer arrete tout.

Au demarrage, la derniere version publiee sur GitHub est comparee a la version
installee ; si elle est plus recente, son installateur est telecharge et lance
en silencieux, puis il relance l'application. Sans internet, ou si GitHub ne
repond pas, l'application demarre simplement telle quelle.

Windows : la mise a jour passe par l'installateur, lance en silencieux.
Linux   : l'archive est telechargee et remplace le dossier du programme, puis on se relance.

Les donnees vivent hors du dossier du programme (%LOCALAPPDATA%\\Bourse sous Windows,
~/.local/share/bourse sous Linux) : une mise a jour ne touche jamais a la base.

Variables d'environnement utiles :
  BOURSE_DONNEES  dossier des donnees (base + sauvegardes)
  BOURSE_TEST=1   ni navigateur, ni mise a jour, ni valeurs d'exemple (tests automatiques)

Usage : python -m backend.lanceur   (depuis la racine du paquet)
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DEPOT = os.environ.get("BOURSE_DEPOT", "GuillaudRemy/bourse")
ARCHIVES = {"nt": "Bourse-Setup.exe", "posix": "bourse-linux-x86_64.tar.gz"}
PORTS = range(8765, 8785)
TEST = os.environ.get("BOURSE_TEST") == "1"


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


def _numeros(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(n) for n in version.lstrip("v").split("."))
    except ValueError:
        return ()


# ── Mise a jour ──────────────────────────────────────────────────────
def _mettre_a_jour() -> bool:
    """Vrai si une mise a jour a ete lancee : il faut alors quitter pour la laisser s'installer.
    Sous Linux, la mise a jour reussie relance directement la nouvelle version (exec)."""
    installee = _version_installee()
    if TEST or installee == "dev" or os.name not in ARCHIVES:
        return False
    nom = ARCHIVES[os.name]
    try:
        requete = urllib.request.Request(
            f"https://api.github.com/repos/{DEPOT}/releases/latest",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "Bourse"},
        )
        with urllib.request.urlopen(requete, timeout=5) as r:
            publication = json.load(r)
        derniere = publication["tag_name"].lstrip("v")
        if _numeros(derniere) <= _numeros(installee):
            return False
        lien = next(a["browser_download_url"] for a in publication["assets"] if a["name"] == nom)
    except Exception as e:     # pas d'internet, GitHub indisponible, publication incomplete…
        print(f"Verification des mises a jour impossible ({e}) : on continue avec la version {installee}.")
        return False

    print(f"Nouvelle version {derniere} (installee : {installee}). Telechargement…")
    try:
        cible = Path(tempfile.gettempdir()) / f"bourse-{derniere}-{nom}"
        with urllib.request.urlopen(lien, timeout=120) as r, open(cible, "wb") as f:
            shutil.copyfileobj(r, f)
        if os.name == "nt":
            _installer_windows(cible)
            return True
        _installer_linux(cible, derniere)
    except Exception as e:
        print(f"Mise a jour impossible ({e}) : on continue avec la version {installee}.")
    return False


def _installer_windows(installateur: Path) -> None:
    print("Installation de la mise a jour : Bourse va se relancer tout seul dans un instant.")
    # Detache : l'installateur doit survivre a ce processus, qui quitte pour liberer ses fichiers.
    subprocess.Popen(
        [str(installateur), "/SILENT", "/SP-", "/NOCANCEL", "/NORESTART", "/SUPPRESSMSGBOXES"],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )


def _installer_linux(archive: Path, version: str) -> None:
    """Extrait a cote, verifie, puis echange les dossiers : en cas d'echec, l'ancien reste en place."""
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
        raise RuntimeError("archive incomplete")

    RACINE.rename(ancien)
    nouveau.rename(RACINE)
    shutil.rmtree(ancien, ignore_errors=True)
    archive.unlink(missing_ok=True)
    print(f"Bourse {version} installe. Redemarrage…")
    sys.stdout.flush()
    os.chdir(RACINE)
    os.execv(str(RACINE / "python" / "bin" / "python3"),
             [str(RACINE / "python" / "bin" / "python3"), "-m", "backend.lanceur"])


# ── Serveur ──────────────────────────────────────────────────────────
def _port_libre() -> int:
    for port in PORTS:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit("Aucun port libre entre 8765 et 8784.")


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

    if _mettre_a_jour():
        time.sleep(2)
        return

    # A fixer avant d'importer le backend : la configuration est lue a l'import.
    donnees = _dossier_donnees()
    os.environ.setdefault("API_PREFIX", "/api")
    os.environ.setdefault("DOSSIER_FRONTEND", str(RACINE / "frontend" / "dist"))
    os.environ.setdefault("DB_NAME", str(donnees / "donnees" / "bourse.db"))
    os.environ.setdefault("DOSSIER_SAUVEGARDES", str(donnees / "sauvegardes"))
    if TEST:
        os.environ.setdefault("ACTUALISATION_AU_DEMARRAGE", "false")

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
    if not TEST:
        threading.Thread(target=_ouvrir_quand_pret, args=(adresse,), daemon=True).start()
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        # La fenetre se fermerait aussitot : on laisse le temps de lire l'erreur.
        print(f"\nErreur : {e}\n")
        if os.name == "nt" and not TEST:
            input("Appuyez sur Entree pour fermer…")
        raise
