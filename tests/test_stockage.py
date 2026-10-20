"""Fusion des comptes case par case et ajustement des divisions d'actions."""
from datetime import date

import pytest
from sqlmodel import Session

from backend import migrate
from backend.db.db import engine
from backend.db.schema import Valeur
from backend.services.stockage import charger_fondamentaux, enregistrer_divisions, enregistrer_fondamentaux
from backend.sources.xbrl import ajuster_divisions, facteur_divisions


def _valeur(db: Session, symbole: str) -> int:
    migrate.main()
    v = Valeur(symbole=symbole, nom=symbole, source="import")
    db.add(v)
    db.commit()
    return v.id


def test_priorite_des_sources():
    with Session(engine) as db:
        vid = _valeur(db, "PRIO")
        enregistrer_fondamentaux(db, vid, {2020: {"bpa": 1.0, "capex": 5.0}}, "yahoo")
        # Source officielle : remplace Yahoo, mais seulement sur les cases qu'elle fournit.
        enregistrer_fondamentaux(db, vid, {2020: {"bpa": 1.1}}, "esef")
        # Saisie manuelle : prioritaire sur tout.
        enregistrer_fondamentaux(db, vid, {2020: {"bpa": 1.2}}, "manuel")
        # Une actualisation ulterieure ne l'ecrase plus.
        enregistrer_fondamentaux(db, vid, {2020: {"bpa": 9.9, "capex": 6.0}}, "yahoo")
        db.commit()

        ligne = charger_fondamentaux(db, vid)[0]
        assert ligne["bpa"] == 1.2 and ligne["sources"]["bpa"] == "manuel"
        assert ligne["capex"] == 6.0 and ligne["sources"]["capex"] == "yahoo"
        assert ligne["source"] == "manuel"


def test_saisie_ajustee_des_divisions_posterieures():
    with Session(engine) as db:
        vid = _valeur(db, "DIV")
        # BPA 2019 publie 11,0 ; division 1 pour 10 en 2022 (apres publication) -> 1,1 aujourd'hui.
        enregistrer_divisions(db, vid, [(date(2022, 6, 1), 10.0), (date(2019, 2, 1), 2.0)])
        enregistrer_fondamentaux(db, vid, {2019: {"bpa": 11.0, "nombre_actions": 100.0}}, "import")
        enregistrer_fondamentaux(db, vid, {2023: {"bpa": 3.0}}, "yahoo")     # Yahoo : deja ajuste
        db.commit()

        par_annee = {f["annee"]: f for f in charger_fondamentaux(db, vid)}
        assert abs(par_annee[2019]["bpa"] - 1.1) < 1e-9
        assert par_annee[2019]["nombre_actions"] == 1000.0
        assert set(par_annee[2019]["ajustes"]) == {"bpa", "nombre_actions"}
        assert par_annee[2023]["bpa"] == 3.0 and not par_annee[2023]["ajustes"]


def test_facteur_divisions():
    divisions = [(date(2014, 6, 9), 7.0), (date(2020, 8, 31), 4.0)]
    assert facteur_divisions(divisions, date(2012, 1, 1)) == 28.0
    assert facteur_divisions(divisions, date(2015, 1, 1)) == 4.0
    assert facteur_divisions(divisions, date(2021, 1, 1)) == 1.0
    assert ajuster_divisions({"bpa": 28.0, "dividende": 2.8, "nombre_actions": 1.0}, 28.0) == \
        pytest.approx({"bpa": 1.0, "dividende": 0.1, "nombre_actions": 28.0})


def test_conversion_en_euros(cours_synthetiques):
    """Cours en USD et taux BCE constant de 2 dollars pour 1 euro : tout est divise par 2,
    sauf le PER, calcule dans la devise des comptes."""
    import pandas as pd

    from backend.services.analyse_service import AnalyseService
    from backend.services.stockage import enregistrer_cours, enregistrer_taux

    with Session(engine) as db:
        migrate.main()
        v = Valeur(symbole="USDTEST", nom="Test USD", source="import", devise="USD")
        db.add(v)
        db.commit()
        df = pd.DataFrame({"jour": cours_synthetiques.index.date, "cloture": cours_synthetiques.to_numpy()})
        enregistrer_cours(db, v.id, df)
        enregistrer_taux(db, "USD", pd.Series(2.0, index=pd.bdate_range("2000-01-03", "2026-01-01")))
        db.commit()

        service = AnalyseService(db)
        dollars, euros = service.analyse(v.id), service.analyse(v.id, en_euros=True)
        assert euros["devise_affichee"] == "EUR"
        assert euros["stats"]["dernier"] == pytest.approx(dollars["stats"]["dernier"] / 2)
        assert euros["regression"]["pente"] == pytest.approx(dollars["regression"]["pente"], abs=1e-9)
