"""Ratios de qualite d'une entreprise, annee par annee, et leur synthese sur 5 et 10 ans.

Entree : les comptes annuels fusionnes (stockage.charger_fondamentaux), postes par action
deja ramenes a la base d'actions actuelle. Un ratio dont un terme manque vaut None :
on ne devine jamais un chiffre absent.
"""
import math

import numpy as np

IMPOT_THEORIQUE = 0.25    # pour le ROIC : les comptes stockes ne detaillent pas l'impot


def _div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def _moyenne(a, b):
    """Moyenne de debut et de fin d'exercice ; la fin seule si le debut manque."""
    if a is None:
        return b
    return (a + b) / 2 if b is not None else a


def ebitda(c: dict) -> float | None:
    """EBITDA publie, sinon resultat operationnel + amortissements (la SEC ne le publie pas)."""
    if c.get("ebitda") is not None:
        return c["ebitda"]
    if c.get("ebit") is not None and c.get("amortissements") is not None:
        return c["ebit"] + abs(c["amortissements"])
    return None


def annuels(comptes: list[dict]) -> list[dict]:
    """Une ligne de ratios par annee (meme ordre que les comptes)."""
    resultat = []
    precedent: dict = {}
    for c in comptes:
        c = {**c, "ebitda": ebitda(c)}
        g = c.get
        dette_nette = g("dette_financiere") - (g("tresorerie") or 0) if g("dette_financiere") is not None else None
        fcf = g("flux_operationnel") - g("capex") if g("flux_operationnel") is not None and g("capex") is not None \
            else None
        capitaux_moyens = _moyenne(precedent.get("capitaux_propres"), g("capitaux_propres"))
        capital_investi = None
        if g("capitaux_propres") is not None and dette_nette is not None:
            capital_investi = g("capitaux_propres") + dette_nette
        capital_employe = g("total_actif") - g("passifs_courants") \
            if g("total_actif") is not None and g("passifs_courants") is not None else None
        nopat = g("ebit") * (1 - IMPOT_THEORIQUE) if g("ebit") is not None else None
        payout = _div(g("dividende"), g("bpa")) if (g("bpa") or 0) > 0 else None

        resultat.append({
            "annee": c["annee"],
            "marge_brute": _div(g("marge_brute"), g("chiffre_affaires")),
            "marge_ebitda": _div(g("ebitda"), g("chiffre_affaires")),
            "marge_operationnelle": _div(g("ebit"), g("chiffre_affaires")),
            "marge_nette": _div(g("benefice_net"), g("chiffre_affaires")),
            "roe": _div(g("benefice_net"), capitaux_moyens) if (capitaux_moyens or 0) > 0 else None,
            "roic": _div(nopat, capital_investi) if (capital_investi or 0) > 0 else None,
            "roce": _div(g("ebit"), capital_employe) if (capital_employe or 0) > 0 else None,
            "dette_nette": dette_nette,
            "dette_nette_ebitda": _div(dette_nette, g("ebitda")) if (g("ebitda") or 0) > 0 else None,
            "gearing": _div(dette_nette, g("capitaux_propres")) if (g("capitaux_propres") or 0) > 0 else None,
            "couverture_interets": _div(g("ebit"), g("charges_interets")) if (g("charges_interets") or 0) > 0
            else None,
            "fcf": fcf,
            "fcf_par_action": _div(fcf, g("nombre_actions")),
            "conversion_fcf": _div(fcf, g("benefice_net")) if (g("benefice_net") or 0) > 0 else None,
            "capex_ca": _div(g("capex"), g("chiffre_affaires")),
            "payout": payout,
            "rotation_actifs": _div(g("chiffre_affaires"), g("total_actif")),
            "liquidite": _div(g("actifs_courants"), g("passifs_courants")),
            "dilution": _div(g("nombre_actions"), precedent.get("nombre_actions")) - 1
            if _div(g("nombre_actions"), precedent.get("nombre_actions")) is not None else None,
        })
        precedent = c
    return resultat


def croissance(comptes: list[dict], cle: str, annees: int) -> float | None:
    """Croissance annuelle moyenne d'un poste sur les `annees` dernieres annees connues,
    par regression de son logarithme (robuste a une annee exceptionnelle). Valeurs positives
    uniquement : une croissance depuis un chiffre negatif n'a pas de sens."""
    points = [(c["annee"], c[cle]) for c in comptes if c.get(cle) is not None]
    if not points:
        return None
    fin = points[-1][0]
    points = [(a, v) for a, v in points if a > fin - annees]
    if len(points) < max(3, annees // 2) or any(v <= 0 for _, v in points):
        return None
    pente, _ = np.polyfit([a for a, _ in points], np.log([v for _, v in points]), 1)
    return float(math.exp(pente) - 1)


def _derniers(serie: list, n: int) -> list[float]:
    return [v for v in serie[-n:] if v is not None]


def synthese(comptes: list[dict], ratios: list[dict]) -> dict:
    """Les chiffres qui resument la qualite d'une entreprise."""
    marges = [r["marge_operationnelle"] for r in ratios]
    dividendes = [c.get("dividende") for c in comptes if c.get("dividende") is not None]
    sans_baisse = 0
    for precedent, actuel in zip(reversed(dividendes[:-1]), reversed(dividendes[1:]), strict=True):
        if actuel >= precedent * 0.995:
            sans_baisse += 1
        else:
            break

    def moyenne(cle, n=5):
        valeurs = _derniers([r[cle] for r in ratios], n)
        return float(np.mean(valeurs)) if valeurs else None

    marges_10 = _derniers(marges, 10)
    nombres = [c.get("nombre_actions") for c in comptes if c.get("nombre_actions")]
    return {
        # Annees reellement couvertes : « 10 ans » ne veut rien dire avec 4 ans de comptes.
        "annees_comptes": len(comptes),
        "annees_marge": len(marges_10),
        "croissance_ca_5": croissance(comptes, "chiffre_affaires", 5),
        "croissance_ca_10": croissance(comptes, "chiffre_affaires", 10),
        "croissance_bpa_5": croissance(comptes, "bpa", 5),
        "croissance_bpa_10": croissance(comptes, "bpa", 10),
        "croissance_dividende_10": croissance(comptes, "dividende", 10),
        "croissance_fcf_10": croissance([{**c, "fcf": r["fcf"]} for c, r in zip(comptes, ratios, strict=True)],
                                        "fcf", 10),
        "roe_moyen_5": moyenne("roe"),
        "roic_moyen_5": moyenne("roic"),
        "marge_operationnelle_moyenne_10": float(np.mean(marges_10)) if marges_10 else None,
        "stabilite_marge_10": float(np.std(marges_10)) if len(marges_10) >= 4 else None,
        "conversion_fcf_moyenne_5": moyenne("conversion_fcf"),
        "dette_nette_ebitda": next((r["dette_nette_ebitda"] for r in reversed(ratios)
                                    if r["dette_nette_ebitda"] is not None), None),
        "dilution_annuelle_5": (nombres[-1] / nombres[-6]) ** (1 / 5) - 1 if len(nombres) >= 6 else None,
        "dividende_sans_baisse": sans_baisse if len(dividendes) > 1 else None,
    }
