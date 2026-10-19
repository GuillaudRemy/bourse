"""Assemble le paquet de bureau dans paquet/ : un Python portable, les bibliotheques,
le backend, l'interface construite et le fichier VERSION.

    python outils/assembler.py 0.2.0 windows   # Python « embeddable » officiel + wheels win_amd64
    python outils/assembler.py 0.2.0 linux     # python-build-standalone (x86_64) -> sortie/bourse-linux-x86_64.tar.gz

La cible windows tourne sous Windows comme sous Linux (pip telecharge alors explicitement
les wheels Windows) ; la cible linux doit tourner sur un Linux x86_64. L'interface doit
etre construite avant : cd frontend && npm ci && npm run build
"""
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

# Windows : derniere 3.12 publiee avec les binaires « embeddable ».
PYTHON_WINDOWS = "3.12.10"
# Linux : build autonome d'astral-sh/python-build-standalone (glibc >= 2.17, Ubuntu 24.04 compris).
PYTHON_LINUX = "3.12.15"
PYTHON_LINUX_BUILD = "20261013"

RACINE = Path(__file__).resolve().parent.parent
PAQUET = RACINE / "paquet"
SORTIE = RACINE / "sortie"
CACHE = RACINE / ".cache"


def _telecharger(url: str) -> Path:
    CACHE.mkdir(exist_ok=True)
    fichier = CACHE / url.rsplit("/", 1)[-1].replace("%2B", "+")
    if not fichier.exists():
        urllib.request.urlretrieve(url, fichier)
    return fichier


def _python_windows() -> None:
    print(f"→ Python portable Windows {PYTHON_WINDOWS}")
    archive = _telecharger(
        f"https://www.python.org/ftp/python/{PYTHON_WINDOWS}/python-{PYTHON_WINDOWS}-embed-amd64.zip")
    with zipfile.ZipFile(archive) as z:
        z.extractall(PAQUET / "python")
    # Le Python embarque ignore site-packages et le dossier parent : on les declare.
    pth = next((PAQUET / "python").glob("python3*._pth"))
    pth.write_text("python312.zip\n.\nLib\\site-packages\n..\nimport site\n")

    print("→ Bibliotheques Windows")
    subprocess.run([
        sys.executable, "-m", "pip", "install", "--quiet", "--no-compile", "--disable-pip-version-check",
        "--target", str(PAQUET / "python" / "Lib" / "site-packages"),
        "--platform", "win_amd64", "--python-version", "3.12", "--implementation", "cp",
        "--only-binary=:all:", "-r", str(RACINE / "backend" / "requirements.txt"),
    ], check=True)


def _python_linux() -> None:
    print(f"→ Python portable Linux {PYTHON_LINUX}")
    nom = f"cpython-{PYTHON_LINUX}%2B{PYTHON_LINUX_BUILD}-x86_64-unknown-linux-gnu-install_only.tar.gz"
    archive = _telecharger(
        f"https://github.com/astral-sh/python-build-standalone/releases/download/{PYTHON_LINUX_BUILD}/{nom}")
    with tarfile.open(archive) as t:
        t.extractall(PAQUET, filter="tar")        # cree paquet/python/

    print("→ Bibliotheques Linux")
    python = PAQUET / "python" / "bin" / "python3"
    subprocess.run([
        str(python), "-m", "pip", "install", "--quiet", "--no-compile", "--disable-pip-version-check",
        "--only-binary=:all:", "-r", str(RACINE / "backend" / "requirements.txt"),
    ], check=True)

    # Allegement : symboles de debogage (libpython en porte ~100 Mo) et modules inutiles ici.
    lib = PAQUET / "python" / "lib"
    for inutile in ("tkinter", "idlelib", "turtledemo", "ensurepip", "site-packages/pip", "lib2to3"):
        shutil.rmtree(lib / "python3.12" / inutile, ignore_errors=True)
    for so in [*lib.glob("libpython*.so*"), *lib.glob("libtcl*.so"), *lib.glob("libtk*.so")]:
        if so.is_file() and not so.is_symlink():
            subprocess.run(["strip", "--strip-unneeded", str(so)], check=True)
    for cache in PAQUET.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)

    for fichier in ("bourse", "installer.sh"):
        shutil.copy(RACINE / "installateur" / "linux" / fichier, PAQUET / fichier)
        (PAQUET / fichier).chmod(0o755)
    shutil.copy(RACINE / "installateur" / "bourse.png", PAQUET / "bourse.png")


def _archiver_linux() -> Path:
    SORTIE.mkdir(exist_ok=True)
    cible = SORTIE / "bourse-linux-x86_64.tar.gz"
    with tarfile.open(cible, "w:gz") as t:
        t.add(PAQUET, arcname="bourse")
    return cible


def main(version: str, cible: str) -> None:
    dist = RACINE / "frontend" / "dist"
    if not (dist / "index.html").exists():
        raise SystemExit("Interface absente : lancez d'abord « npm run build » dans frontend/.")

    shutil.rmtree(PAQUET, ignore_errors=True)
    PAQUET.mkdir()
    _python_windows() if cible == "windows" else _python_linux()

    print("→ Application")
    shutil.copytree(RACINE / "backend", PAQUET / "backend",
                    ignore=shutil.ignore_patterns("__pycache__", ".env"))
    shutil.copytree(dist, PAQUET / "frontend" / "dist")
    (PAQUET / "VERSION").write_text(version.lstrip("v") + "\n")
    print(f"Paquet {cible} {version} pret dans {PAQUET}")

    if cible == "linux":
        print(f"Archive : {_archiver_linux()}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[2] not in ("windows", "linux"):
        raise SystemExit("Usage : python outils/assembler.py <version> windows|linux")
    main(sys.argv[1], sys.argv[2])
