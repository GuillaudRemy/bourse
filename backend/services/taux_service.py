"""Taux sans risque : rendement des emprunts d'Etat a 10 ans, reference du DCF.

Le taux d'actualisation par defaut du DCF = taux sans risque de la devise des comptes + prime de risque
des actions (reglage, 5 % par defaut). Quand les taux montent, le rendement exige d'une action monte aussi :
une valeur fixe de 8 % surevaluait les actions en 2023 (taux a 3 %) et les sous-evaluait en 2020 (taux negatifs).
"""
from datetime import timedelta

import pandas as pd
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session, col, select

from backend.core import reglages
from backend.db.schema import TauxSansRisque
from backend.sources import bce, yahoo
from backend.sources.base import SourceIndisponible

ZONES = {
    "EUR": ("bce", "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", "emprunts d'État notés AAA de la zone euro à 10 ans (BCE)"),
    "USD": ("yahoo", "^TNX", "emprunts du Trésor américain à 10 ans"),
}
PRIME_DEFAUT = 5.0                       # % : prime de risque des actions, ordre de grandeur historique
BORNES = (0.06, 0.15)                    # actualisation par defaut, comme les curseurs de l'interface


def zone(devise: str | None) -> str:
    """Zone dont le taux sert de reference : le dollar pour des comptes en dollars, l'euro sinon."""
    return "USD" if (devise or "").upper() == "USD" else "EUR"


def actualiser(db: Session) -> list[str]:
    """Telecharge les nouvelles observations de chaque zone (une fois par lot d'actualisation)."""
    avertissements = []
    for code, (source, cle, libelle) in ZONES.items():
        dernier = db.exec(select(func.max(TauxSansRisque.jour)).where(TauxSansRisque.zone == code)).first()
        debut = dernier - timedelta(days=10) if dernier else None
        try:
            if source == "bce":
                df = bce.serie(cle, debut)
            else:
                df = yahoo.cours_recents(cle, debut)[0] if debut else yahoo.cours_et_divisions(cle)[0]
        except SourceIndisponible as e:
            avertissements.append(f"Taux sans risque ({libelle}) : {e}")
            continue
        if df is None or df.empty:
            continue
        lignes = [{"zone": code, "jour": j, "taux": float(t)} for j, t in zip(df["jour"], df["cloture"], strict=True)
                  if pd.notna(t)]
        table = TauxSansRisque.__table__  # type: ignore[attr-defined]
        for i in range(0, len(lignes), 500):
            requete = insert(table).values(lignes[i:i + 500])
            db.exec(requete.on_conflict_do_update(index_elements=["zone", "jour"], set_={"taux": requete.excluded.taux}))
    db.commit()
    return avertissements


def dernier(db: Session, devise: str | None) -> dict | None:
    """Dernier taux connu de la zone, en fraction, avec sa date et son libelle ; None s'il n'est pas encore telecharge."""
    code = zone(devise)
    ligne = db.exec(select(TauxSansRisque).where(TauxSansRisque.zone == code)
                    .order_by(col(TauxSansRisque.jour).desc()).limit(1)).first()
    if not ligne:
        return None
    return {"zone": code, "taux": ligne.taux / 100, "jour": ligne.jour.isoformat(), "libelle": ZONES[code][2]}


def prime() -> float:
    return reglages.nombre("prime_risque", PRIME_DEFAUT) / 100


def actualisation_par_defaut(sans_risque: dict | None) -> float | None:
    """Taux sans risque + prime, arrondi au demi-point et borne ; None sans taux sans risque."""
    if not sans_risque:
        return None
    brut = sans_risque["taux"] + prime()
    return min(max(round(brut * 200) / 200, BORNES[0]), BORNES[1])
