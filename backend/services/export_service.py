"""Exports Excel : fiche d'une valeur et portefeuille (un onglet par theme)."""
import io

import pandas as pd
from sqlmodel import Session, select

from backend.db.champs import CHAMPS
from backend.db.schema import Valeur
from backend.services.analyse_service import AnalyseService
from backend.services.portefeuille_service import PortefeuilleService
from backend.services.stockage import charger_cours

LIBELLES_FICHE = {
    "dernier": "Dernier cours", "variation_jour": "Variation du jour", "perf_1an": "Performance 1 an",
    "perf_5ans": "Performance 5 ans", "pente": "Pente de la droite (/an)", "ecart_type": "Écart-type du couloir",
    "position": "Position (σ)", "zone_libelle": "Zone", "fiabilite": "Fiabilité de la droite", "annees": "Années analysées",
    "note": "Note de qualité", "roic": "ROIC moyen 5 ans", "croissance_bpa_10": "Croissance du BPA",
    "dette_nette_ebitda": "Dette nette / EBITDA", "per": "PER", "rendement_dividende": "Rendement du dividende",
    "dcf_inverse": "Croissance supposée (DCF inversé)", "rsi": "RSI 14", "volatilite": "Volatilité 1 an",
}


def _classeur(onglets: dict[str, pd.DataFrame]) -> bytes:
    sortie = io.BytesIO()
    with pd.ExcelWriter(sortie, engine="openpyxl") as ecrivain:
        for nom, df in onglets.items():
            df.to_excel(ecrivain, sheet_name=nom[:31], index=False)
            feuille = ecrivain.sheets[nom[:31]]
            for colonne in feuille.columns:          # largeur de colonne lisible
                largeur = max(len(str(c.value or "")) for c in colonne[:200])
                feuille.column_dimensions[colonne[0].column_letter].width = min(max(10, largeur + 2), 60)
    return sortie.getvalue()


def valeur(db: Session, valeur_id: int) -> tuple[str, bytes]:
    v = db.get(Valeur, valeur_id)
    service = AnalyseService(db)
    analyse = service.analyse(valeur_id)
    fiche = service.fiche_resumee(v)
    resume = pd.DataFrame([{"Indicateur": libelle, "Valeur": fiche.get(cle)} for cle, libelle in LIBELLES_FICHE.items()])
    cours = charger_cours(db, valeur_id).resample("ME").last().dropna(subset=["cloture"])
    noms = {"jour": "Fin de mois", "cloture": "Clôture", "ajuste": "Dividendes réinvestis", "ouverture": "Ouverture",
            "haut": "Plus haut", "bas": "Plus bas", "volume": "Volume"}
    cours = cours.reset_index().rename(columns=noms)
    cours["Fin de mois"] = cours["Fin de mois"].dt.date
    comptes = pd.DataFrame([{"Année": f["annee"], **{c.libelle: f.get(c.cle) for c in CHAMPS}, "PER moyen": f.get("per")}
                            for f in analyse.get("fondamentaux", [])])
    onglets = {"Résumé": resume, "Cours mensuels": cours, "Comptes annuels": comptes}
    if analyse.get("comptes"):
        onglets["Ratios"] = pd.DataFrame(analyse["comptes"]["ratios"])
    if analyse.get("valorisation") and analyse["valorisation"].get("historique"):
        onglets["Multiples"] = pd.DataFrame(analyse["valorisation"]["historique"])
    nom = f"{v.symbole.replace('^', '')}-{v.nom[:30]}".replace("/", "-").replace(" ", "_")
    return nom, _classeur(onglets)


def portefeuille(db: Session, compte_id: int | None = None) -> bytes:
    service = PortefeuilleService(db)
    s = service.synthese(compte_id)
    noms = {v.id: v.nom for v in db.exec(select(Valeur))}
    operations = pd.DataFrame([{**t.model_dump(), "valeur": noms.get(t.valeur_id)} for t in service.transactions(compte_id)])
    onglets = {"Opérations": operations}
    if not s.get("vide"):
        onglets = {"Positions": pd.DataFrame(s["positions"]), **onglets}
        for c in s["fiscalite"]["comptes"]:
            if c.get("annees"):
                onglets[f"Fiscalité {c['nom']}"] = pd.DataFrame(c["annees"])
    return _classeur(onglets)
