"""Assemble le paquet Windows dans paquet/ : Python « embeddable » officiel,
bibliotheques en version Windows, backend, interface construite et VERSION.

    python outils/assembler.py 0.2.0

Tourne sous Windows (chaine de publication GitHub) comme sous Linux (pip telecharge
alors explicitement les wheels win_amd64). L'interface doit etre construite avant :
cd frontend && npm ci && npm run build
"""
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

PYTHON_VERSION = "3.12.10"     # derniere 3.12 publiee avec les binaires Windows
RACINE = Path(__file__).resolve().parent.parent
PAQUET = RACINE / "paquet"
CACHE = RACINE / ".cache"


def main(version: str) -> None:
    dist = RACINE / "frontend" / "dist"
    if not (dist / "index.html").exists():
        raise SystemExit("Interface absente : lancez d'abord « npm run build » dans frontend/.")

    shutil.rmtree(PAQUET, ignore_errors=True)
    CACHE.mkdir(exist_ok=True)

    print(f"→ Python portable {PYTHON_VERSION}")
    archive = CACHE / f"python-{PYTHON_VERSION}-embed-amd64.zip"
    if not archive.exists():
        urllib.request.urlretrieve(
            f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip", archive)
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

    print("→ Application")
    shutil.copytree(RACINE / "backend", PAQUET / "backend",
                    ignore=shutil.ignore_patterns("__pycache__", ".env"))
    shutil.copytree(dist, PAQUET / "frontend" / "dist")
    (PAQUET / "VERSION").write_text(version.lstrip("v") + "\n")
    print(f"Paquet {version} pret dans {PAQUET}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage : python outils/assembler.py <version>")
    main(sys.argv[1])
