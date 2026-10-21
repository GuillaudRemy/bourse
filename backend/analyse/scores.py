"""Scores synthetiques classiques, et une note maison transparente.

  · Piotroski F-score (0 a 9) : solidite financiere et amelioration d'une annee sur l'autre.
  · Altman Z-score : risque de faillite (modele d'origine, entreprises industrielles ;
    peu pertinent pour les banques et assurances).
  · Beneish M-score : probabilite de manipulation comptable (au-dessus de -1,78 : vigilance).

Chaque critere est renvoye avec sa valeur et son explication : un score n'est utile que si
l'on comprend d'ou il vient. Un critere incalculable (donnee absente) est marque comme tel
et n'entre pas dans le total.
"""
from backend.analyse.ratios import _div


def _critere(nom: str, ok: bool | None, detail: str) -> dict:
    return {"nom": nom, "ok": ok, "detail": detail}


def piotroski(avant: dict, precedent: dict, actuel: dict) -> dict:
    """Compare l'annee `actuel` a `precedent` ; `avant` (l'annee d'avant, peut etre vide)
    sert aux ratios rapportes a l'actif de debut d'exercice."""
    v, p, a = avant.get, precedent.get, actuel.get
    roa, roa_avant = _div(a("benefice_net"), p("total_actif")), _div(p("benefice_net"), v("total_actif"))
    levier, levier_avant = _div(a("dette_long_terme"), a("total_actif")), _div(p("dette_long_terme"), p("total_actif"))
    liquidite = _div(a("actifs_courants"), a("passifs_courants"))
    liquidite_avant = _div(p("actifs_courants"), p("passifs_courants"))
    marge, marge_avant = _div(a("marge_brute"), a("chiffre_affaires")), _div(p("marge_brute"), p("chiffre_affaires"))
    rotation = _div(a("chiffre_affaires"), p("total_actif"))
    rotation_avant = _div(p("chiffre_affaires"), v("total_actif"))

    def compare(x, y, sens=1):
        return None if x is None or y is None else (x - y) * sens > 0

    criteres = [
        _critere("Rentabilité positive (ROA > 0)", None if roa is None else roa > 0, "Bénéfice net / actif"),
        _critere("Flux opérationnel positif", None if a("flux_operationnel") is None else a("flux_operationnel") > 0,
                 "L'activité génère de la trésorerie"),
        _critere("ROA en hausse", compare(roa, roa_avant), "Rentabilité de l'actif meilleure que l'an passé"),
        _critere("Bénéfice de qualité (flux > bénéfice)",
                 None if a("flux_operationnel") is None or a("benefice_net") is None
                 else a("flux_operationnel") > a("benefice_net"), "Le bénéfice se retrouve en trésorerie"),
        _critere("Endettement long terme en baisse", compare(levier, levier_avant, -1), "Dette LT / actif"),
        _critere("Liquidité en hausse", compare(liquidite, liquidite_avant), "Actifs / passifs courants"),
        _critere("Pas de dilution", None if a("nombre_actions") is None or p("nombre_actions") is None
                 else a("nombre_actions") <= p("nombre_actions") * 1.005, "Nombre d'actions stable ou en baisse"),
        _critere("Marge brute en hausse", compare(marge, marge_avant), "Pouvoir de fixation des prix"),
        _critere("Rotation de l'actif en hausse", compare(rotation, rotation_avant), "CA / actif"),
    ]
    evalues = [c for c in criteres if c["ok"] is not None]
    score = sum(1 for c in evalues if c["ok"])
    return {"annee": actuel["annee"], "score": score, "sur": len(evalues), "criteres": criteres,
            "lecture": None if len(evalues) < 6 else
            "solide" if score >= 7 else "moyen" if score >= 4 else "fragile"}


def altman(comptes: dict, capitalisation: float | None) -> dict | None:
    g = comptes.get
    actif = g("total_actif")
    if not actif or g("total_passif") is None:
        return None
    termes = {
        "Fonds de roulement / actif": (1.2, _div((g("actifs_courants") or 0) - (g("passifs_courants") or 0), actif)
                                        if g("actifs_courants") is not None and g("passifs_courants") is not None
                                        else None),
        "Réserves / actif": (1.4, _div(g("resultats_non_distribues"), actif)),
        "EBIT / actif": (3.3, _div(g("ebit"), actif)),
        "Capitalisation / dettes": (0.6, _div(capitalisation, g("total_passif"))),
        "Chiffre d'affaires / actif": (1.0, _div(g("chiffre_affaires"), actif)),
    }
    if any(v is None for _, v in termes.values()):
        manquants = [n for n, (_, v) in termes.items() if v is None]
        return {"annee": comptes["annee"], "z": None, "manquants": manquants}
    z = sum(poids * v for poids, v in termes.values())
    zone = "sûre" if z > 2.99 else "grise" if z >= 1.81 else "détresse"
    return {"annee": comptes["annee"], "z": z, "zone": zone,
            "termes": [{"nom": n, "poids": p, "valeur": v} for n, (p, v) in termes.items()]}


def beneish(precedent: dict, actuel: dict) -> dict | None:
    p, a = precedent.get, actuel.get
    if not (a("chiffre_affaires") and p("chiffre_affaires") and a("total_actif") and p("total_actif")):
        return None

    def ratio(x, y):
        return _div(x, y)

    variables = {}
    variables["DSRI"] = ratio(_div(a("creances_clients"), a("chiffre_affaires")),
                              _div(p("creances_clients"), p("chiffre_affaires")))
    variables["GMI"] = ratio(_div(p("marge_brute"), p("chiffre_affaires")),
                             _div(a("marge_brute"), a("chiffre_affaires")))

    def qualite_actif(x):
        if x("actifs_courants") is None or x("immobilisations_corporelles") is None:
            return None
        return 1 - (x("actifs_courants") + x("immobilisations_corporelles")) / x("total_actif")
    variables["AQI"] = ratio(qualite_actif(a), qualite_actif(p))
    variables["SGI"] = a("chiffre_affaires") / p("chiffre_affaires")

    def amortissement(x):
        if x("amortissements") is None or x("immobilisations_corporelles") is None:
            return None
        return _div(x("amortissements"), x("amortissements") + x("immobilisations_corporelles"))
    variables["DEPI"] = ratio(amortissement(p), amortissement(a))
    variables["SGAI"] = ratio(_div(a("frais_generaux"), a("chiffre_affaires")),
                              _div(p("frais_generaux"), p("chiffre_affaires")))

    def levier(x):
        if x("passifs_courants") is None or x("dette_long_terme") is None:
            return None
        return (x("passifs_courants") + x("dette_long_terme")) / x("total_actif")
    variables["LVGI"] = ratio(levier(a), levier(p))
    variables["TATA"] = _div(a("benefice_net") - a("flux_operationnel"), a("total_actif")) \
        if a("benefice_net") is not None and a("flux_operationnel") is not None else None

    poids = {"DSRI": 0.92, "GMI": 0.528, "AQI": 0.404, "SGI": 0.892, "DEPI": 0.115, "SGAI": -0.172,
             "TATA": 4.679, "LVGI": -0.327}
    neutre = {k: (0.0 if k == "TATA" else 1.0) for k in poids}
    manquants = [k for k, v in variables.items() if v is None]
    if variables["TATA"] is None or len(manquants) > 3:
        return {"annee": actuel["annee"], "m": None, "manquants": manquants}
    m = -4.84 + sum(poids[k] * (v if v is not None else neutre[k]) for k, v in variables.items())
    return {"annee": actuel["annee"], "m": m, "vigilance": m > -1.78, "manquants": manquants,
            "variables": variables}


def note_maison(synthese: dict) -> dict:
    """Note de qualite sur 100, critere par critere. Les seuils reprennent les reperes
    habituels de l'investissement « qualite » ; un critere sans donnee ne compte pas."""
    s = synthese.get
    regles = [
        ("Rentabilité du capital (ROIC moyen 5 ans)", 20, s("roic_moyen_5"),
         lambda v: 20 if v >= 0.15 else 12 if v >= 0.10 else 5 if v >= 0.06 else 0, "≥ 15 % : excellent"),
        ("Stabilité de la marge opérationnelle (10 ans)", 15, s("stabilite_marge_10"),
         lambda v: 15 if v <= 0.02 else 9 if v <= 0.04 else 3 if v <= 0.07 else 0, "écart-type ≤ 2 points"),
        ("Croissance du chiffre d'affaires (10 ans)", 15, s("croissance_ca_10"),
         lambda v: 15 if v >= 0.07 else 10 if v >= 0.04 else 5 if v >= 0.02 else 0, "≥ 7 % par an"),
        ("Croissance du BPA (10 ans)", 15, s("croissance_bpa_10"),
         lambda v: 15 if v >= 0.09 else 10 if v >= 0.05 else 4 if v >= 0.02 else 0, "≥ 9 % par an"),
        ("Endettement (dette nette / EBITDA)", 15, s("dette_nette_ebitda"),
         lambda v: 15 if v <= 1 else 10 if v <= 2 else 4 if v <= 3 else 0, "≤ 1 an d'EBITDA"),
        ("Conversion du bénéfice en trésorerie (5 ans)", 10, s("conversion_fcf_moyenne_5"),
         lambda v: 10 if v >= 0.9 else 6 if v >= 0.7 else 2 if v >= 0.5 else 0, "FCF ≥ 90 % du bénéfice"),
        ("Pas de dilution des actionnaires (5 ans)", 10, s("dilution_annuelle_5"),
         lambda v: 10 if v <= 0 else 6 if v <= 0.01 else 0, "nombre d'actions stable ou en baisse"),
    ]
    criteres, points, maximum = [], 0, 0
    for nom, plafond, valeur, bareme, repere in regles:
        obtenus = bareme(valeur) if valeur is not None else None
        criteres.append({"nom": nom, "valeur": valeur, "points": obtenus, "plafond": plafond, "repere": repere})
        if obtenus is not None:
            points += obtenus
            maximum += plafond
    annees = s("annees_comptes") or 0
    if maximum < 50 or annees < 3:
        return {"note": None, "criteres": criteres, "couverture": maximum, "annees": annees}
    return {"note": round(100 * points / maximum), "criteres": criteres, "couverture": maximum, "annees": annees,
            "provisoire": annees < 8}
