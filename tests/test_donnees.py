"""Version 0.6.1 : simulateur, controles des donnees, contre-verification, robustesse de l'actualisation, AMF."""
from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from backend.analyse import controles
from backend.analyse.simulateur import Poche, simuler
from backend.db.db import engine
from backend.db.schema import Correction, Valeur
from backend.main import app
from backend.services import taches
from backend.services.stockage import enregistrer_fondamentaux, journaliser_correction_cours
from backend.sources import amf, contre_verification


def test_simulateur_fonds_garanti_et_fourchette():
    # Fonds garanti a 2 % : resultat certain, egal a la capitalisation des versements.
    r = simuler([Poche("fonds_euros", 1.0, 0.02, 0.0)], versement=100, capital=0, annees=10)
    attendu = sum(100 * 1.02 ** ((120 - m) / 12) for m in range(1, 121))
    assert r["jalons"][-1]["p50"] == pytest.approx(attendu, rel=0.002) and r["jalons"][-1]["proba_perte"] == 0
    r = simuler([Poche("actions", 0.5, 0.07, 0.16), Poche("or", 0.5, 0.05, 0.15)], 300, 1000, 20)
    fin = r["jalons"][-1]
    assert fin["p10"] < fin["p25"] < fin["p50"] < fin["p75"] < fin["p90"] and fin["verse"] == 1000 + 300 * 240
    assert [j["annees"] for j in r["jalons"]] == [10, 15, 20]
    with pytest.raises(ValueError):
        simuler([Poche("actions", 0.6, 0.07, 0.16)], 100, 0, 10)


def test_simulateur_api():
    with TestClient(app) as client:
        assert "actions" in client.get("/simulateur/classes").json()["classes"]
        poche = {"classe": "actions", "part": 1, "rendement": 0.07, "volatilite": 0.16}
        corps = {"versement": 200, "annees": 10, "poches": [poche]}
        assert client.post("/simulateur", json=corps).json()["jalons"][0]["annees"] == 10
        corps["poches"][0]["part"] = 0.5
        assert client.post("/simulateur", json=corps).status_code == 422


def test_controle_des_comptes():
    propres = [{"annee": a, "chiffre_affaires": 1e9 * 1.05 ** i, "benefice_net": 1e8, "nombre_actions": 1e7, "bpa": 10.0,
                "capitaux_propres": 5e8, "flux_operationnel": 1.5e8, "capex": 5e7, "source": "esef", "sources": {}}
               for i, a in enumerate(range(2015, 2025))]
    bon = controles.comptes(propres)
    assert bon["statut"] == "ok" and not bon["controles"] and bon["annees"] == 10
    fautifs = [dict(f) for f in propres]
    fautifs[5]["chiffre_affaires"] *= 1000           # erreur d'unite
    fautifs[7]["bpa"] = 25.0                         # BPA incoherent
    mauvais = controles.comptes(fautifs)
    textes = " ".join(c["texte"] for c in mauvais["controles"])
    assert "multiplié" in textes and "BPA publié" in textes and mauvais["score"] < bon["score"]


def test_rendement_total_recalcule():
    jours = pd.bdate_range("2020-01-01", periods=300)
    cours = pd.DataFrame({"cloture": 100.0}, index=jours)
    dividendes = pd.Series([2.0], index=[jours[150]])
    facteur = np.where(jours < jours[150], 0.98, 1.0)
    cours["ajuste"] = cours["cloture"] * facteur
    assert controles.rendement_total(cours, dividendes)["statut"] == "ok"
    cours["ajuste"] = cours["cloture"]               # Yahoo aurait oublie le dividende
    r = controles.rendement_total(cours, dividendes)
    assert r["ecart_max"] == pytest.approx(-0.02) and r["statut"] == "attention"


def test_contre_verification():
    jours = pd.bdate_range("2025-01-01", periods=10)
    yahoo = pd.Series(100.0, index=jours)
    autre = yahoo.copy()
    assert contre_verification.comparer(yahoo, autre, "Euronext")["statut"] == "ok"
    autre.iloc[3] = 90.0
    r = contre_verification.comparer(yahoo, autre, "Euronext")
    assert r["desaccords"] == 1 and r["statut"] == "attention" and r["jour_ecart_max"] == jours[3].strftime("%Y-%m-%d")
    assert contre_verification.couvre("MC.PA", "PAR", "action") and contre_verification.couvre("AAPL", "NMS", "action")
    assert not contre_verification.couvre("SAP.DE", "GER", "action")
    assert not contre_verification.couvre("BTC-EUR", "CCC", "crypto")


def test_journal_des_corrections():
    with Session(engine) as db:
        v = Valeur(symbole="CORR1", nom="Corrigee", source="import")
        db.add(v)
        db.commit()
        assert v.id is not None
        # Le 6/01 (dernier jour connu, peut-etre en cours de seance) change aussi : ce n'est pas une correction.
        avant = {date(2025, 1, 2): 100.0, date(2025, 1, 3): 101.0, date(2025, 1, 6): 102.0}
        nouveaux = pd.DataFrame({"jour": [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)], "cloture": [100.0, 110.0, 99.0]})
        journaliser_correction_cours(db, v.id, nouveaux, avant)
        enregistrer_fondamentaux(db, v.id, {2024: {"chiffre_affaires": 1000.0}}, "esef")
        enregistrer_fondamentaux(db, v.id, {2024: {"chiffre_affaires": 1100.0}}, "esef")     # revise par sa source
        enregistrer_fondamentaux(db, v.id, {2024: {"chiffre_affaires": 1100.0}}, "esef")     # inchange : rien
        db.commit()
        corrections = db.exec(select(Correction).where(Correction.valeur_id == v.id)).all()
        assert sorted(c.type for c in corrections) == ["comptes", "cours"]
        assert "1 séance(s)" in next(c.detail for c in corrections if c.type == "cours")
    with TestClient(app) as client:
        c = client.get(f"/valeurs/{v.id}/controles").json()
        assert len(c["corrections"]) == 2
        assert any(x["id"] == v.id for x in client.get("/donnees/couverture").json()["valeurs"])


def test_echecs_d_affilee_et_valeur_morte(monkeypatch):
    with Session(engine) as db:
        v = Valeur(symbole="MORTE1", nom="Morte", source="yahoo")
        db.add(v)
        db.commit()
        vid = v.id
    assert vid is not None

    def panne(self, *a, **k):
        raise HTTPException(502, "Symbole inconnu")
    monkeypatch.setattr("backend.services.valeur_service.ValeurService.actualiser", panne)
    assert taches._actualiser_une(vid, "Morte", "cours", dernier_essai=False) is False
    with Session(engine) as db:
        assert db.get(Valeur, vid).echecs == 0                  # premier essai : rien n'est compte
    for _ in range(taches.ABANDON):
        taches._actualiser_une(vid, "Morte", "cours")
    with Session(engine) as db:
        v = db.get(Valeur, vid)
        assert v.echecs == taches.ABANDON and "Symbole inconnu" in v.derniere_erreur
    assert taches._actualiser_une(vid, "Morte", "cours") is True       # ignoree par l'actualisation rapide
    assert taches._actualiser_une(vid, "Morte", "complet") is False    # « Tout mettre a jour » reessaie


def test_documents_amf(monkeypatch):
    reponse = {"result": [
        {"anneeComptable": 2018, "typesDocument": ["DocumentReference"], "dateInformation": "2019-03-01T00:00:00",
         "societes": [{"raisonSociale": "LVMH MOET HENNESSY-LOUIS VUITTON"}],
         "documents": [{"nomFichier": "2019-0208.pdf", "path": "a/visa.pdf", "accessible": True},
                       {"nomFichier": "2019-020800.pdf", "path": "a/doc.pdf", "accessible": True}]},
        {"anneeComptable": 2018, "typesDocument": ["DocumentReference"], "dateInformation": "2019-04-01T00:00:00",
         "societes": [{"raisonSociale": "REMY COINTREAU"}],
         "documents": [{"nomFichier": "2019-0618.pdf", "path": "b/x.pdf", "accessible": True}]},
    ]}
    monkeypatch.setattr(amf, "json_", lambda *a, **k: reponse)
    documents = amf.documents("LVMH Moët Hennessy - Louis Vuitton, Société Européenne")
    assert documents == [{"annee": 2018, "type": "DocumentReference", "date": "2019-03-01", "fichier": "2019-020800.pdf",
                          "chemin": "a/doc.pdf"}]
    with pytest.raises(amf.SourceIndisponible):
        amf.telecharger("../../etc/passwd")


def test_echelle_esef_corrigee():
    from backend.sources.esef import corriger_echelle
    capgemini_2022 = {"bpa": 8_790_000.0, "nombre_actions": 176_019_736e6, "benefice_net": 1_547e6}
    corrige = corriger_echelle(capgemini_2022)
    assert corrige["bpa"] == pytest.approx(8.79) and corrige["nombre_actions"] == pytest.approx(176_019_736)
    normal = {"bpa": 9.37, "nombre_actions": 177_396_346.0, "benefice_net": 1_663e6}
    assert corriger_echelle(normal) == normal
