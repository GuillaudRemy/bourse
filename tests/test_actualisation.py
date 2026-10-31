"""Actualisation rapide : seances recentes seulement, sauf si l'historique doit etre recharge."""
from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.core import reglages
from backend.db.db import engine
from backend.db.schema import Valeur
from backend.main import app
from backend.services import taches
from backend.services.stockage import charger_cours
from backend.services.valeur_service import ValeurService
from backend.sources import yahoo, yahoo_direct


def _serie(debut: date, fin: date, decalage: float = 0.0) -> pd.DataFrame:
    jours = [d.date() for d in pd.bdate_range(debut, fin)]
    prix = [100 + (j - date(2020, 1, 1)).days * 0.01 + decalage for j in jours]   # meme jour = meme prix
    return pd.DataFrame({"jour": jours, "ouverture": prix, "haut": prix, "bas": prix, "cloture": prix,
                         "ajuste": prix, "volume": [1000.0] * len(jours)})


@pytest.fixture
def faux_yahoo(monkeypatch):
    """Historique complet jusqu'a hier ; `etat` pilote ce que renvoie la periode recente."""
    etat = {"complets": 0, "evenement": False, "decalage": 0.0}
    hier = date.today() - timedelta(days=1)

    def complet(symbole):
        etat["complets"] += 1
        return _serie(date(2020, 1, 1), hier), []

    def recents(symbole, debut):
        nouvelle = _serie(debut, hier + timedelta(days=3))
        return nouvelle.assign(cloture=nouvelle["cloture"] + etat["decalage"]), etat["evenement"]

    for module in (yahoo, yahoo_direct):
        monkeypatch.setattr(module, "cours_et_divisions", complet)
        monkeypatch.setattr(module, "cours_recents", recents)
    return etat


def test_veille_horaire():
    maintenant = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
    with TestClient(app):
        reglages.ecrire("derniere_tentative", (maintenant - timedelta(minutes=59)).isoformat())
        assert not taches.cours_perimes(maintenant)
        reglages.ecrire("derniere_tentative", (maintenant - timedelta(minutes=60)).isoformat())
        assert taches.cours_perimes(maintenant)
        reglages.ecrire("actualisation_auto", "non")
        assert not taches.cours_perimes(maintenant)
        reglages.ecrire("actualisation_auto", "oui")


def test_coupure_pendant_la_veille_ne_compte_pas(monkeypatch):
    """Une coupure internet ne doit pas faire abandonner les valeurs : seule la veille horaire est tolerante."""
    def panne(self, *a, **k):
        raise HTTPException(502, "pas de reseau")
    monkeypatch.setattr(ValeurService, "actualiser", panne)
    with TestClient(app), Session(engine) as db:
        v = Valeur(symbole="VEILLE.PA", nom="Veille", source="yahoo", devise="EUR")
        db.add(v)
        db.commit()
        assert not taches._actualiser_une(v.id, v.nom, "horaire")
        db.refresh(v)
        assert v.echecs == 0
        assert not taches._actualiser_une(v.id, v.nom, "cours")
        db.refresh(v)
        assert v.echecs == 1


def test_seances_recentes_ou_rechargement(faux_yahoo):
    with TestClient(app), Session(engine) as db:
        v = Valeur(symbole="INCR.PA", nom="Incrementale", type="etf", source="yahoo", devise="EUR")
        db.add(v)
        db.commit()
        service = ValeurService(db)
        service.actualiser(v.id, complet=False, change=False, recents=True)      # premier passage : tout
        assert faux_yahoo["complets"] == 1
        avant = len(charger_cours(db, v.id))

        r = service.actualiser(v.id, complet=False, change=False, recents=True)  # rien de special : recent
        assert faux_yahoo["complets"] == 1 and "nouvelle(s) séance(s)" in r.message
        assert len(charger_cours(db, v.id)) > avant

        faux_yahoo["evenement"] = True                                            # dividende : tout recharger
        service.actualiser(v.id, complet=False, change=False, recents=True)
        assert faux_yahoo["complets"] == 2

        faux_yahoo.update(evenement=False, decalage=5.0)                          # historique corrige
        service.actualiser(v.id, complet=False, change=False, recents=True)
        assert faux_yahoo["complets"] == 3
