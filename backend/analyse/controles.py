"""Controles de vraisemblance des donnees : comptes annuels et rendement total.

On signale, on ne corrige pas (meme principe que qualite.py pour les cours). Chaque comptes publies
est verifie par des identites simples qu'une erreur de saisie, d'unite (milliers / millions) ou de
fusion de sources casse presque toujours. Un score de confiance resume le tout sur 100.
"""
import pandas as pd

ESSENTIELS = ("chiffre_affaires", "benefice_net", "bpa", "nombre_actions", "capitaux_propres", "flux_operationnel", "capex")
OFFICIELLES = {"esef", "sec", "manuel", "import", "pdf"}


def _relatif(a: float | None, b: float | None) -> float | None:
    return None if not a or not b else abs(a / b - 1)


def comptes(fondamentaux: list[dict]) -> dict:
    """{"score", "statut", "annees", "completude", "officielles", "controles": [{annee, gravite, texte}]}."""
    lignes = sorted((f for f in fondamentaux if any(f.get(c) is not None for c in ESSENTIELS)), key=lambda f: f["annee"])
    if not lignes:
        return {"score": None, "statut": "inconnu", "annees": 0, "completude": 0.0, "officielles": 0.0, "controles": []}
    controles: list[dict] = []

    def signaler(annee, gravite, texte):
        controles.append({"annee": annee, "gravite": gravite, "texte": texte})

    for f in lignes:
        a = f["annee"]
        if f.get("benefice_net") and f.get("nombre_actions") and f.get("bpa"):
            calcule = f["benefice_net"] / f["nombre_actions"]
            ecart = _relatif(f["bpa"], calcule)
            if ecart is not None and ecart > 0.15 and abs(f["bpa"] - calcule) > 0.05:
                signaler(a, "attention", f"BPA publié {f['bpa']:.2f} ≠ bénéfice net ÷ nombre d'actions {calcule:.2f} "
                                         f"(écart {ecart:.0%}) : nombre d'actions ou unité à vérifier")
        if f.get("total_actif") and f.get("total_passif") is not None and f.get("capitaux_propres") is not None:
            ecart = _relatif(f["total_passif"] + f["capitaux_propres"], f["total_actif"])
            if ecart is not None and ecart > 0.10:
                signaler(a, "attention", f"Bilan déséquilibré de {ecart:.0%} (actif ≠ dettes + capitaux propres ; "
                                         "intérêts minoritaires ou poste manquant ?)")
        if f.get("benefice_net") and f.get("chiffre_affaires") and f["benefice_net"] > f["chiffre_affaires"] > 0:
            signaler(a, "attention", "Bénéfice supérieur au chiffre d'affaires : plus-value exceptionnelle, ou erreur ?")
        if f.get("capitaux_propres") is not None and f["capitaux_propres"] < 0:
            signaler(a, "info", "Capitaux propres négatifs (rachats d'actions massifs ou pertes accumulées)")

    for avant, apres in zip(lignes, lignes[1:], strict=False):
        a = apres["annee"]
        if a - avant["annee"] > 1:
            signaler(a, "attention", f"Années manquantes entre {avant['annee']} et {a}")
        for cle, libelle in (("chiffre_affaires", "Chiffre d'affaires"), ("nombre_actions", "Nombre d'actions")):
            x, y = avant.get(cle), apres.get(cle)
            if x and y and x > 0 and y > 0 and (y / x > 5 or x / y > 5):
                signaler(a, "alerte", f"{libelle} multiplié par {y / x:.2g} en un an : erreur d'unité (milliers / "
                                      "millions), division d'actions non ajustée, ou fusion ?")

    cases = [(f.get(c) is not None, (f.get("sources") or {}).get(c) or f.get("source")) for f in lignes for c in ESSENTIELS]
    presentes = [s for ok, s in cases if ok]
    completude = len(presentes) / len(cases)
    officielles = sum(1 for s in presentes if s in OFFICIELLES) / len(presentes) if presentes else 0.0
    penalite = sum({"alerte": 15, "attention": 5}.get(c["gravite"], 0) for c in controles)
    score = round(max(0.0, min(100.0, 40 * completude + 20 * officielles + 40 * min(len(lignes), 10) / 10 - penalite)))
    statut = "ok" if score >= 70 else "attention" if score >= 40 else "alerte"
    return {"score": score, "statut": statut, "annees": len(lignes), "premiere": lignes[0]["annee"],
            "derniere": lignes[-1]["annee"], "completude": completude, "officielles": officielles,
            "controles": sorted(controles, key=lambda c: -c["annee"])}


def rendement_total(cours: pd.DataFrame, dividendes: pd.Series) -> dict | None:
    """Recalcule le cours ajuste (dividendes reinvestis) a partir des clotures et des dividendes conserves,
    et le compare a celui de Yahoo : un ecart revele un dividende oublie, en double ou mal converti."""
    if cours.empty or dividendes.empty or cours["ajuste"].isna().all():
        return None
    cloture = cours["cloture"]
    facteur = pd.Series(1.0, index=cloture.index)
    for jour, montant in dividendes.items():
        precedentes = cloture[cloture.index < jour]
        if precedentes.empty or precedentes.iloc[-1] <= 0:
            continue
        facteur[facteur.index < jour] *= 1 - montant / precedentes.iloc[-1]
    calcule = cloture * facteur
    yahoo = cours["ajuste"]
    ecart = (calcule / yahoo - 1).dropna()
    if ecart.empty:
        return None
    pire = ecart.abs().idxmax()
    resultat = {
        "dividendes": int(len(dividendes)), "premier_dividende": dividendes.index[0].strftime("%Y-%m-%d"),
        "ecart_max": float(ecart[pire]), "jour_ecart_max": pire.strftime("%Y-%m-%d"),
        "ecart_debut": float(ecart.iloc[0]),
    }
    pire_ecart = abs(resultat["ecart_max"])
    resultat["statut"] = "ok" if pire_ecart < 0.02 else "attention" if pire_ecart < 0.10 else "alerte"
    return resultat
