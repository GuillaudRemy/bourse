"""Mises a jour : ordre des versions, canal beta, signature et empreintes."""
import base64
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend import mise_a_jour as maj


def test_ordre_des_versions():
    assert maj.cle_version("0.5.0") > maj.cle_version("0.5.0-beta.2") > maj.cle_version("0.5.0-beta.1")
    assert maj.cle_version("0.5.0-beta.1") > maj.cle_version("0.4.9") > maj.cle_version("0.4.0")
    assert maj.cle_version("v0.10.0") > maj.cle_version("0.9.9")
    assert maj.cle_version("dev") == ()


@pytest.fixture
def depot(tmp_path, monkeypatch):
    """Publications locales au format GitHub, et une cle de signature de test."""
    cle = Ed25519PrivateKey.generate()
    publique = base64.b64encode(cle.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    monkeypatch.setattr(maj, "CLE_PUBLIQUE", publique.decode())
    monkeypatch.setattr(maj.verifier_signature, "__defaults__", (publique.decode(),))

    def publier(version, contenu=b"installateur", beta=False, signer=True, alterer=False):
        dossier = tmp_path / version
        dossier.mkdir()
        (dossier / "Bourse-Setup.exe").write_bytes(contenu)
        sommes = f"{maj.empreinte(dossier / 'Bourse-Setup.exe')}  Bourse-Setup.exe\n".encode()
        (dossier / maj.SOMMES).write_bytes(sommes)
        if signer:
            (dossier / maj.SIGNATURE).write_bytes(base64.b64encode(cle.sign(sommes)))
        if alterer:
            (dossier / "Bourse-Setup.exe").write_bytes(contenu + b" modifie")
        return {"tag_name": f"v{version}", "prerelease": beta,
                "assets": [{"name": f.name, "browser_download_url": f.as_uri()} for f in dossier.iterdir()]}

    def lister(*publications):
        liste = tmp_path / "publications.json"
        liste.write_text(json.dumps(list(publications)))
        monkeypatch.setattr(maj, "API", liste.as_uri())
    return publier, lister


def test_canal_stable_et_beta(depot):
    publier, lister = depot
    lister(publier("0.5.0"), publier("0.6.0-beta.1", beta=True))
    assert maj.chercher("0.4.0", beta=False).version == "0.5.0"
    assert maj.chercher("0.4.0", beta=True).version == "0.6.0-beta.1"
    assert maj.chercher("0.5.0", beta=False) is None
    assert maj.chercher("0.4.0", beta=True, ignorees={"0.6.0-beta.1"}).version == "0.5.0"


def test_telechargement_verifie(depot, tmp_path):
    publier, lister = depot
    lister(publier("0.5.0", b"le bon installateur"))
    fichier = maj.telecharger(maj.chercher("0.4.0", beta=False), "Bourse-Setup.exe", tmp_path / "telechargements")
    assert fichier.read_bytes() == b"le bon installateur"


@pytest.mark.parametrize("probleme", ["alterer", "non_signee", "autre_cle"])
def test_mise_a_jour_refusee(depot, tmp_path, monkeypatch, probleme):
    publier, lister = depot
    lister(publier("0.5.0", alterer=probleme == "alterer", signer=probleme != "non_signee"))
    if probleme == "autre_cle":
        autre = Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        monkeypatch.setattr(maj.verifier_signature, "__defaults__", (base64.b64encode(autre).decode(),))
    with pytest.raises(maj.VerificationEchouee):
        maj.telecharger(maj.chercher("0.4.0", beta=False), "Bourse-Setup.exe", tmp_path / "telechargements")
    assert not list((tmp_path / "telechargements").glob("*")) if (tmp_path / "telechargements").exists() else True


def test_canal_beta_lu_dans_la_base(tmp_path):
    import sqlite3
    base = tmp_path / "bourse.db"
    assert maj.canal_beta(base) is False
    with sqlite3.connect(base) as c:
        c.execute("CREATE TABLE reglage (cle TEXT PRIMARY KEY, valeur TEXT)")
        c.execute("INSERT INTO reglage VALUES ('canal_beta', 'oui')")
    assert maj.canal_beta(base) is True
