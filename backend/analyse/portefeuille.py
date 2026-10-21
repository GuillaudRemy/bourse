"""Calculs de portefeuille, independants de la base : positions, valeur quotidienne,
performance (TWR, XIRR), comparaison a un indice, risque.

Conventions :
  · tous les montants sont en euros ; `montant` d'une transaction est le flux de tresorerie
    du compte (+ entree d'argent : vente, dividende, depot ; - sortie : achat, frais, retrait) ;
  · prix de revient unitaire (PRU) : moyenne ponderee des achats, frais compris ;
  · flux externes : depots et retraits s'il y en a ; sinon, chaque achat est considere comme
    un apport et chaque vente comme un retrait (portefeuille sans suivi des especes) ;
  · divisions d'actions : un releve donne les quantites REELLEMENT echangees, alors que les cours
    historiques sont ajustes des divisions. Chaque quantite est donc ramenee a la base d'actions
    actuelle (30 Apple achetees en 2019 = 120 aujourd'hui). Une transaction « division » saisie a
    la main ne sert que pour les valeurs dont on ne connait pas les divisions.
"""
import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

SEANCES = 252


@dataclass
class Ligne:
    valeur_id: int
    quantite: float = 0.0
    cout: float = 0.0                 # cout de revient restant (EUR)
    plus_value_realisee: float = 0.0
    dividendes: float = 0.0
    frais: float = 0.0
    premier_achat: date | None = None
    ventes: list = field(default_factory=list)    # (jour, plus-value) pour la fiscalite

    @property
    def pru(self) -> float | None:
        return self.cout / self.quantite if self.quantite > 1e-9 else None


def facteur(divisions: dict[Any, list], valeur_id: int | None, jour: date) -> float:
    """Multiplicateur d'une quantite echangee le `jour` vers la base d'actions actuelle."""
    resultat = 1.0
    for d, ratio in divisions.get(valeur_id, []):
        if d > jour:
            resultat *= ratio
    return resultat


def _manuelle(t: dict, divisions: dict[Any, list]) -> bool:
    """Division saisie a la main : prise en compte seulement si les divisions sont inconnues."""
    return t["type"] == "division" and not divisions.get(t.get("valeur_id"))


def positions(transactions: list[dict], divisions: dict[Any, list] | None = None) -> dict[int, Ligne]:
    """Rejoue les transactions dans l'ordre chronologique (quantites en base d'actions actuelle)."""
    divisions = divisions or {}
    lignes: dict[int, Ligne] = {}
    for t in sorted(transactions, key=lambda t: (t["jour"], t["id"] or 0)):
        vid = t.get("valeur_id")
        if vid is None:
            continue
        ligne = lignes.setdefault(vid, Ligne(valeur_id=vid))
        quantite = (t.get("quantite") or 0.0) * (facteur(divisions, vid, t["jour"]) if t["type"] in ("achat", "vente") else 1)
        frais, montant = t.get("frais") or 0.0, t.get("montant") or 0.0
        if t["type"] == "achat":
            ligne.cout += -montant if montant else 0.0          # montant d'un achat : negatif, frais compris
            ligne.quantite += quantite
            ligne.frais += frais
            ligne.premier_achat = ligne.premier_achat or t["jour"]
        elif t["type"] == "vente" and ligne.quantite > 0:
            vendue = min(quantite, ligne.quantite)
            cout_sorti = ligne.cout * vendue / ligne.quantite
            plus_value = montant - cout_sorti                     # montant d'une vente : net de frais
            ligne.plus_value_realisee += plus_value
            ligne.ventes.append((t["jour"], plus_value))
            ligne.cout -= cout_sorti
            ligne.quantite -= vendue
            ligne.frais += frais
        elif t["type"] == "dividende":
            ligne.dividendes += montant
        elif _manuelle(t, divisions) and quantite > 0:             # quantite = ratio (2 pour 1 -> 2)
            ligne.quantite *= quantite
        elif t["type"] == "frais":
            ligne.frais += -montant
    return lignes


def flux_externes(transactions: list[dict]) -> pd.Series:
    """Argent apporte (+) ou retire (-) par l'investisseur, par jour."""
    avec_especes = any(t["type"] in ("depot", "retrait") for t in transactions)
    flux: dict[date, float] = {}
    for t in transactions:
        m = t.get("montant") or 0.0
        if avec_especes and t["type"] in ("depot", "retrait"):
            flux[t["jour"]] = flux.get(t["jour"], 0.0) + m
        elif not avec_especes and t["type"] in ("achat", "vente"):
            flux[t["jour"]] = flux.get(t["jour"], 0.0) - m        # achat (m < 0) = apport
    if not flux:
        return pd.Series(dtype=float)
    serie = pd.Series(flux)
    serie.index = pd.to_datetime(serie.index)
    return serie.sort_index()


def valeur_quotidienne(transactions: list[dict], prix_eur: dict[int, pd.Series],
                       divisions: dict[Any, list] | None = None) -> pd.DataFrame:
    """Valeur de marche quotidienne (titres + especes) et flux externes du jour.
    `prix_eur` : cloture en euros de chaque valeur, indexee par date."""
    divisions = divisions or {}
    if not transactions:
        return pd.DataFrame(columns=["valeur", "flux"])
    debut = pd.Timestamp(min(t["jour"] for t in transactions))
    jours = pd.bdate_range(debut, pd.Timestamp.today().normalize())
    avec_especes = any(t["type"] in ("depot", "retrait") for t in transactions)

    quantites = pd.DataFrame(0.0, index=jours, columns=sorted(prix_eur))
    especes = pd.Series(0.0, index=jours)
    for t in sorted(transactions, key=lambda t: t["jour"]):
        jour = pd.Timestamp(t["jour"])
        if jour > jours[-1]:
            continue
        a_partir = jours >= jour
        vid, q = t.get("valeur_id"), t.get("quantite") or 0.0
        if vid in quantites.columns:
            if t["type"] in ("achat", "vente"):
                q *= facteur(divisions, vid, t["jour"])
            if t["type"] == "achat":
                quantites.loc[a_partir, vid] += q
            elif t["type"] == "vente":
                quantites.loc[a_partir, vid] -= q
            elif _manuelle(t, divisions) and q > 0:
                quantites.loc[a_partir, vid] *= q
        m = t.get("montant") or 0.0
        if avec_especes or t["type"] in ("dividende", "frais"):
            especes[a_partir] += m

    prix = pd.DataFrame({vid: s.reindex(jours.union(s.index)).ffill().reindex(jours) for vid, s in prix_eur.items()})
    titres = (quantites * prix.reindex(columns=quantites.columns)).fillna(0).sum(axis=1)
    flux = flux_externes(transactions).reindex(jours).fillna(0.0) if len(jours) else pd.Series(dtype=float)
    return pd.DataFrame({"valeur": titres + especes, "titres": titres, "especes": especes, "flux": flux})


def twr(quotidien: pd.DataFrame) -> pd.Series:
    """Performance cumulee ponderee par le temps : neutralise les apports et retraits."""
    valeur, flux = quotidien["valeur"], quotidien["flux"]
    precedent = valeur.shift(1)
    rendements = ((valeur - flux) / precedent - 1).where(precedent > 0).fillna(0.0)
    rendements[~np.isfinite(rendements)] = 0.0
    return (1 + rendements).cumprod() - 1


def xirr(flux: list[tuple[date, float]]) -> float | None:
    """Taux de rendement interne annuel de flux dates (convention investisseur : apport < 0)."""
    if len(flux) < 2 or not any(m > 0 for _, m in flux) or not any(m < 0 for _, m in flux):
        return None
    t0 = min(j for j, _ in flux)
    annees = np.array([(j - t0).days / 365.25 for j, _ in flux])
    montants = np.array([m for _, m in flux])

    def vna(taux):
        return float(np.sum(montants / (1 + taux) ** annees))

    bas, haut = -0.99, 10.0
    if vna(bas) * vna(haut) > 0:
        return None
    for _ in range(200):
        milieu = (bas + haut) / 2
        if vna(bas) * vna(milieu) <= 0:
            haut = milieu
        else:
            bas = milieu
    return (bas + haut) / 2


def flux_investisseur(quotidien: pd.DataFrame) -> list[tuple[date, float]]:
    flux = [(j.date(), -float(f)) for j, f in quotidien["flux"].items() if abs(f) > 1e-9]
    if len(quotidien):
        flux.append((quotidien.index[-1].date(), float(quotidien["valeur"].iloc[-1])))
    return flux


def reference(quotidien: pd.DataFrame, prix_reference: pd.Series) -> pd.DataFrame:
    """Le meme argent, aux memes dates, place dans l'indice de reference (dividendes reinvestis)."""
    prix = prix_reference.reindex(quotidien.index.union(prix_reference.index)).ffill().reindex(quotidien.index)
    parts = (quotidien["flux"] / prix).fillna(0).cumsum()
    return pd.DataFrame({"valeur": parts * prix, "flux": quotidien["flux"]})


def risque(rendements_cumules: pd.Series, reference_cumulee: pd.Series | None = None) -> dict:
    niveau = 1 + rendements_cumules
    quotidiens = niveau.pct_change().dropna()
    quotidiens = quotidiens[np.isfinite(quotidiens)]
    if len(quotidiens) < 20:
        return {}
    resultat = {
        "volatilite": float(quotidiens.std() * math.sqrt(SEANCES)),
        "perte_max": float((niveau / niveau.cummax() - 1).min()),
    }
    if reference_cumulee is not None:
        ref = (1 + reference_cumulee).pct_change().reindex(quotidiens.index).dropna()
        commun = quotidiens.reindex(ref.index)
        if len(ref) > 20 and ref.var() > 0:
            resultat["beta"] = float(np.cov(commun, ref)[0, 1] / ref.var())
            resultat["correlation"] = float(np.corrcoef(commun, ref)[0, 1])
    return resultat


def repartition(lignes: list[dict], cle: str) -> list[dict]:
    """Poids de chaque groupe (secteur, pays, devise…) dans la valeur des titres."""
    total = sum(l["valeur_actuelle"] or 0 for l in lignes)
    groupes: dict[str, float] = {}
    for l in lignes:
        nom = l.get(cle) or "Non renseigné"
        groupes[nom] = groupes.get(nom, 0.0) + (l["valeur_actuelle"] or 0)
    return sorted(({"nom": n, "valeur": v, "poids": v / total if total else 0} for n, v in groupes.items()),
                  key=lambda g: -g["valeur"])


def correlations(prix_eur: dict[int, pd.Series], annees: int = 3) -> dict:
    """Correlations des rendements hebdomadaires sur les dernieres annees."""
    if len(prix_eur) < 2:
        return {}
    df = pd.DataFrame(prix_eur).resample("W").last()
    df = df[df.index >= df.index.max() - pd.DateOffset(years=annees)].pct_change().dropna(how="all")
    matrice = df.corr(min_periods=26)
    return {"ids": [int(c) for c in matrice.columns],
            "valeurs": [[None if pd.isna(v) else round(float(v), 3) for v in ligne] for ligne in matrice.to_numpy()]}
