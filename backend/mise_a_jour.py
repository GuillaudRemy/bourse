"""Recherche, telechargement et verification des mises a jour (utilise par le lanceur).

Chaque publication contient, en plus des installateurs :
  SHA256SUMS      empreinte SHA-256 de chaque fichier ;
  SHA256SUMS.sig  signature Ed25519 de SHA256SUMS, faite par la CI avec une cle privee
                  gardee dans les secrets GitHub.
L'application ne connait que la cle publique : une archive qui ne correspond pas a une
empreinte signee par cette cle n'est jamais installee, meme si GitHub etait compromis.

Canal beta : les « pre-versions » GitHub (0.5.0-beta.1…) ne sont proposees qu'aux
installations ou le reglage « canal_beta » vaut « oui ».

Bibliotheque standard seulement (plus `cryptography` pour la signature) : ce module est
importe avant le backend.
"""
import base64
import hashlib
import json
import os
import re
import shutil
import sqlite3
import urllib.request
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

DEPOT = os.environ.get("BOURSE_DEPOT", "GuillaudRemy/bourse")
# Tests de mise a jour en CI : adresse (http:// ou file://) d'une liste de publications au format GitHub.
API = os.environ.get("BOURSE_MAJ_API") or f"https://api.github.com/repos/{DEPOT}/releases?per_page=20"
CLE_PUBLIQUE = os.environ.get("BOURSE_CLE_PUBLIQUE") or "K0fuPOI0bnefwAXSdkciWeWFPtH0eEXNx668RdFNTe0="
SOMMES, SIGNATURE = "SHA256SUMS", "SHA256SUMS.sig"


class VerificationEchouee(Exception):
    """Archive non signee, signature invalide ou empreinte differente : on n'installe pas."""


@dataclass
class Publication:
    version: str
    beta: bool
    fichiers: dict[str, str]          # nom -> adresse de telechargement


def cle_version(version: str) -> tuple[int, ...]:
    """« 0.5.0 » > « 0.5.0-beta.2 » > « 0.5.0-beta.1 » > « 0.4.9 ». () si illisible."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:-beta\.?(\d+))?", version.strip())
    if not m:
        return ()
    majeur, mineur, correctif, beta = m.groups()
    return (int(majeur), int(mineur), int(correctif), 0 if beta else 1, int(beta or 0))


def _lire(adresse: str, delai: float) -> bytes:
    requete = urllib.request.Request(adresse, headers={"Accept": "application/vnd.github+json", "User-Agent": "Bourse"})
    with urllib.request.urlopen(requete, timeout=delai) as r:
        return r.read()


def canal_beta(base: Path) -> bool:
    """Reglage lu directement dans la base : le backend n'est pas encore charge."""
    if not base.exists():
        return False
    try:
        with sqlite3.connect(f"file:{base}?mode=ro", uri=True, timeout=2) as connexion:
            ligne = connexion.execute("SELECT valeur FROM reglage WHERE cle = 'canal_beta'").fetchone()
        return bool(ligne) and (ligne[0] or "").strip().lower() == "oui"
    except sqlite3.Error:
        return False


def chercher(installee: str, beta: bool, ignorees: Collection[str] = frozenset(), delai: float = 5) -> Publication | None:
    """Publication plus recente que `installee` (None sinon). `ignorees` : versions deja
    abandonnees apres un echec de demarrage, a ne pas reproposer."""
    publications = json.loads(_lire(API, delai))
    if isinstance(publications, dict):        # /releases/latest renvoie un objet seul
        publications = [publications]
    candidates = []
    for p in publications:
        version = p["tag_name"].lstrip("v")
        if p.get("draft") or (p.get("prerelease") and not beta) or version in ignorees or not cle_version(version):
            continue
        candidates.append(Publication(version, bool(p.get("prerelease")),
                                      {a["name"]: a["browser_download_url"] for a in p.get("assets", [])}))
    if not candidates:
        return None
    meilleure = max(candidates, key=lambda p: cle_version(p.version))
    return meilleure if cle_version(meilleure.version) > cle_version(installee) else None


def empreinte(fichier: Path) -> str:
    h = hashlib.sha256()
    with open(fichier, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def verifier_signature(sommes: bytes, signature: bytes, cle_publique: str = CLE_PUBLIQUE) -> None:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(cle_publique)).verify(base64.b64decode(signature.strip()), sommes)
    except (InvalidSignature, ValueError) as e:
        raise VerificationEchouee("signature invalide : la mise a jour ne vient pas du depot officiel") from e


def verifier_fichier(fichier: Path, nom: str, sommes: bytes) -> None:
    attendues = {}
    for ligne in sommes.decode().splitlines():
        if ligne.strip():
            valeur, _, fichier_nom = ligne.strip().partition("  ")
            attendues[fichier_nom.lstrip("*")] = valeur.lower()
    if nom not in attendues:
        raise VerificationEchouee(f"{nom} absent de {SOMMES}")
    if empreinte(fichier) != attendues[nom]:
        raise VerificationEchouee(f"empreinte de {nom} differente : fichier corrompu ou modifie")


def telecharger(publication: Publication, nom: str, dossier: Path, delai: float = 300) -> Path:
    """Telecharge `nom` et le verifie ; supprime le fichier et leve VerificationEchouee sinon."""
    for requis in (nom, SOMMES, SIGNATURE):
        if requis not in publication.fichiers:
            raise VerificationEchouee(f"publication {publication.version} sans {requis} : non verifiable")
    sommes = _lire(publication.fichiers[SOMMES], 60)
    verifier_signature(sommes, _lire(publication.fichiers[SIGNATURE], 60))
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / f"bourse-{publication.version}-{nom}"
    requete = urllib.request.Request(publication.fichiers[nom], headers={"User-Agent": "Bourse"})
    with urllib.request.urlopen(requete, timeout=delai) as r, open(cible, "wb") as f:
        shutil.copyfileobj(r, f)
    try:
        verifier_fichier(cible, nom, sommes)
    except VerificationEchouee:
        cible.unlink(missing_ok=True)
        raise
    return cible
