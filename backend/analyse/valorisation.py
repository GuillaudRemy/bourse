"""Valorisation : multiples (compares a leur propre historique) et modeles de valeur intrinseque.

Comme la droite le fait pour le cours, chaque multiple est situe dans sa propre histoire :
un PER de 25 est cher pour un constructeur automobile, normal pour une marque de luxe.

Modeles (tous par action, devise des comptes) :
  · DCF : free cash flow par action projete `annees` ans a `croissance`, puis croissance
    perpetuelle `terminale`, actualise a `actualisation` ;
  · DCF inverse : la croissance que le cours actuel suppose — souvent plus parlant qu'un prix ;
  · Gordon : dividende / (taux - croissance), pour les valeurs de rendement ;
  · Graham : racine(22,5 x BPA x actif net par action) ;
  · PEG : PER / croissance du BPA (en points).
Une valeur intrinseque n'est jamais un chiffre exact : on presente une fourchette.
"""
import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from backend.analyse.ratios import _div, ebitda, lecteur

ANNEES_HISTORIQUE = 20


def _fr(v: float, decimales: int = 2) -> str:
    return f"{v:,.{decimales}f}".replace(",", " ").replace(".", ",")


def _pc(v: float) -> str:
    return f"{v * 100:+.1f} %".replace(".", ",")


def multiples_annuels(cloture: pd.Series, comptes: list[dict]) -> list[dict]:
    """Multiples de fin d'annee : cours du dernier jour de cotation de l'exercice."""
    if cloture.empty:
        return []
    fin = cloture.groupby(cloture.index.year).last()
    resultat = []
    for c in comptes:
        if c["annee"] not in fin.index:
            continue
        resultat.append(_multiples(float(fin[c["annee"]]), c) | {"annee": c["annee"]})
    return resultat


def _multiples(cours: float, c: dict) -> dict:
    g = lecteur(c)
    capitalisation = cours * g("nombre_actions") if g("nombre_actions") else None
    dette_nette = g("dette_financiere") - (g("tresorerie") or 0) if g("dette_financiere") is not None else None
    ve = capitalisation + dette_nette if capitalisation is not None and dette_nette is not None else None
    fcf = g("flux_operationnel") - g("capex") if g("flux_operationnel") is not None and g("capex") is not None \
        else None
    positif = lambda x: x if x is not None and x > 0 else None  # noqa: E731 — un multiple sur un negatif n'a pas de sens
    return {
        "per": _div(cours, positif(g("bpa"))),
        "ve_ebitda": _div(ve, positif(ebitda(c))),
        "ve_ebit": _div(ve, positif(g("ebit"))),
        "ve_ca": _div(ve, positif(g("chiffre_affaires"))),
        "p_b": _div(capitalisation, positif(g("capitaux_propres"))),
        "p_fcf": _div(capitalisation, positif(fcf)),
        "rendement_fcf": _div(fcf, capitalisation),
        "rendement_dividende": _div(g("dividende"), cours),
        "capitalisation": capitalisation,
        "valeur_entreprise": ve,
    }


MULTIPLES = ["per", "ve_ebitda", "ve_ebit", "ve_ca", "p_b", "p_fcf", "rendement_fcf", "rendement_dividende"]
# Pour les rendements, plus haut = moins cher : le percentile se lit a l'envers.
INVERSES = {"rendement_fcf", "rendement_dividende"}


def situer(cours_actuel: float, comptes: list[dict], historique: list[dict]) -> dict:
    """Multiples actuels (dernier exercice, cours du jour) et leur percentile dans l'historique."""
    if not comptes:
        return {}
    actuels = _multiples(cours_actuel, comptes[-1])
    resultat = {"actuels": actuels, "historique": {}}
    for cle in MULTIPLES:
        serie = [h[cle] for h in historique[-ANNEES_HISTORIQUE:] if h.get(cle) is not None]
        valeur = actuels.get(cle)
        if len(serie) < 3 or valeur is None:
            continue
        rang = float(np.mean([v <= valeur for v in serie]))
        cherte = 1 - rang if cle in INVERSES else rang      # 1 = le plus cher de son histoire
        resultat["historique"][cle] = {
            "min": float(np.min(serie)), "mediane": float(np.median(serie)), "max": float(np.max(serie)),
            "percentile": rang, "cherte": cherte, "annees": len(serie),
        }
    return resultat


# ── Modeles de valeur intrinseque ────────────────────────────────────
@dataclass
class Hypotheses:
    croissance: float = 0.06       # des flux, les `annees` premieres annees
    annees: int = 10
    terminale: float = 0.02        # croissance perpetuelle ensuite
    actualisation: float = 0.08    # rendement exige
    base_fcf: float | None = None  # FCF par action de depart (None = moyenne des 3 derniers)


def _dcf(base: float, h: Hypotheses) -> float | None:
    if h.actualisation <= h.terminale:
        return None
    valeur, flux = 0.0, base
    for annee in range(1, h.annees + 1):
        flux *= 1 + h.croissance
        valeur += flux / (1 + h.actualisation) ** annee
    terminale = flux * (1 + h.terminale) / (h.actualisation - h.terminale)
    return valeur + terminale / (1 + h.actualisation) ** h.annees


def dcf_inverse(cours: float, base: float, h: Hypotheses) -> float | None:
    """Croissance annuelle (sur `annees` ans) qui egalise la valeur DCF et le cours."""
    if base <= 0:
        return None
    bas, haut = -0.5, 1.0
    for _ in range(80):
        milieu = (bas + haut) / 2
        valeur = _dcf(base, Hypotheses(milieu, h.annees, h.terminale, h.actualisation))
        if valeur is None:
            return None
        if valeur < cours:
            bas = milieu
        else:
            haut = milieu
    return (bas + haut) / 2 if -0.49 < bas < 0.99 else None


def hypotheses_par_defaut(comptes: list[dict], synthese: dict) -> Hypotheses:
    """Croissance prudente : celle du FCF ou du BPA sur 10 ans, bornee entre 0 et 12 %."""
    candidate = synthese.get("croissance_fcf_10") or synthese.get("croissance_bpa_10") \
        or synthese.get("croissance_bpa_5") or 0.04
    return Hypotheses(croissance=round(min(max(candidate, 0.0), 0.12), 3))


def fcf_par_action(comptes: list[dict]) -> float | None:
    """Moyenne des 3 derniers FCF par action connus (lisse une annee exceptionnelle)."""
    valeurs = []
    for c in reversed(comptes):
        if c.get("flux_operationnel") is not None and c.get("capex") is not None and c.get("nombre_actions"):
            valeurs.append((c["flux_operationnel"] - c["capex"]) / c["nombre_actions"])
        if len(valeurs) == 3:
            break
    return float(np.mean(valeurs)) if valeurs else None


def modeles(cours: float, comptes: list[dict], synthese: dict, h: Hypotheses) -> dict:
    dernier = comptes[-1] if comptes else {}
    base = h.base_fcf if h.base_fcf is not None else fcf_par_action(comptes)
    resultats: list[dict[str, Any]] = []

    if base and base > 0:
        valeur = _dcf(base, h)
        resultats.append({"cle": "dcf", "nom": "DCF (flux de trésorerie actualisés)", "valeur": valeur,
                          "detail": f"FCF par action de départ {_fr(base)}, {_pc(h.croissance)}/an sur {h.annees} ans, "
                                    f"puis {_pc(h.terminale)}/an, actualisé à {_pc(h.actualisation)[1:]}"})
    dividende = dernier.get("dividende")
    g_div = synthese.get("croissance_dividende_10")
    if dividende and dividende > 0:
        g = min(g_div if g_div is not None else h.terminale, h.actualisation - 0.01, 0.06)
        resultats.append({"cle": "gordon", "nom": "Gordon (dividendes)",
                          "valeur": dividende * (1 + g) / (h.actualisation - g),
                          "detail": f"dividende {_fr(dividende)}, croissance {_pc(g)}/an, taux {_pc(h.actualisation)[1:]}"})
    bpa = dernier.get("bpa")
    actif_net = _div(dernier.get("capitaux_propres"), dernier.get("nombre_actions"))
    if bpa and bpa > 0 and actif_net and actif_net > 0:
        resultats.append({"cle": "graham", "nom": "Nombre de Graham", "valeur": math.sqrt(22.5 * bpa * actif_net),
                          "detail": f"√(22,5 × BPA {_fr(bpa)} × actif net par action {_fr(actif_net)})"})

    for r in resultats:
        r["marge_securite"] = (r["valeur"] / cours - 1) if r["valeur"] else None

    croissance_bpa = synthese.get("croissance_bpa_5") or synthese.get("croissance_bpa_10")
    per = _div(cours, bpa) if bpa and bpa > 0 else None
    valeurs = [r["valeur"] for r in resultats if r["valeur"]]
    return {
        "hypotheses": asdict(h) | {"base_fcf": base},
        "modeles": resultats,
        "fourchette": {"bas": min(valeurs), "haut": max(valeurs), "mediane": float(np.median(valeurs))}
        if valeurs else None,
        "dcf_inverse": dcf_inverse(cours, base, h) if base and base > 0 else None,
        "peg": _div(per, croissance_bpa * 100) if per and croissance_bpa and croissance_bpa > 0 else None,
        "cours": cours,
    }
