"""Empreintes et signature des fichiers d'une publication.

    python outils/signer.py <dossier> <fichier>...   ecrit <dossier>/SHA256SUMS et SHA256SUMS.sig
    python outils/signer.py --verifier <dossier>      verifie la signature et chaque empreinte

La cle privee (Ed25519, base64) est lue dans la variable CLE_SIGNATURE (secret GitHub) ;
la cle publique correspondante est inscrite dans backend/mise_a_jour.py.
"""
import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import mise_a_jour  # noqa: E402


def signer(dossier: Path, fichiers: list[Path]) -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    cle = os.environ.get("CLE_SIGNATURE", "").strip()
    if not cle:
        sys.exit("CLE_SIGNATURE absente : impossible de signer la publication.")
    prive = Ed25519PrivateKey.from_private_bytes(base64.b64decode(cle))
    sommes = "".join(f"{mise_a_jour.empreinte(f)}  {f.name}\n" for f in fichiers).encode()
    (dossier / mise_a_jour.SOMMES).write_bytes(sommes)
    (dossier / mise_a_jour.SIGNATURE).write_text(base64.b64encode(prive.sign(sommes)).decode() + "\n")
    # Garde-fou : la cle du secret doit correspondre a celle que connait l'application.
    mise_a_jour.verifier_signature(sommes, (dossier / mise_a_jour.SIGNATURE).read_bytes())
    print(sommes.decode(), end="")


def verifier(dossier: Path) -> None:
    sommes = (dossier / mise_a_jour.SOMMES).read_bytes()
    mise_a_jour.verifier_signature(sommes, (dossier / mise_a_jour.SIGNATURE).read_bytes())
    for ligne in sommes.decode().splitlines():
        nom = ligne.partition("  ")[2]
        mise_a_jour.verifier_fichier(dossier / nom, nom, sommes)
        print(f"ok  {nom}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--verifier":
        verifier(Path(sys.argv[2]))
    elif len(sys.argv) >= 3:
        signer(Path(sys.argv[1]), [Path(f) for f in sys.argv[2:]])
    else:
        sys.exit(__doc__)
