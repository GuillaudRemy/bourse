"""Les trois verifications avant de prolonger une droite de regression vers l'avenir.

1. Historique : au moins 20 ans, pour avoir traverse plusieurs cycles.
2. PER : la pente doit etre portee par la croissance des benefices, pas par un
   gonflement du PER (une renotation ne se produit qu'une fois).
3. Rupture : l'entreprise doit etre restee fidele a elle-meme.

« La droite donne le cadre, les comptes la valident. »
"""
import numpy as np
import pandas as pd
from backend.analyse.regression import Regression, ajuster

ANNEES_MIN = 20
ANNEES_RECENTES = 7     # fenetre comparee a la pente complete pour detecter une rupture

ORDRE = {"ok": 0, "inconnu": 1, "attention": 2, "alerte": 3}


def _verification(cle, titre, statut, texte, **details) -> dict:
    return {"cle": cle, "titre": titre, "statut": statut, "texte": texte, "details": details}


def historique(reg: Regression) -> dict:
    annees = (reg.fin - reg.debut).days / 365.25
    if annees >= ANNEES_MIN:
        statut, texte = "ok", f"{annees:.0f} ans d'historique : plusieurs cycles traversés."
    elif annees >= 10:
        statut, texte = "attention", (
            f"{annees:.0f} ans seulement : la pente peut dépendre du point de départ "
            f"(creux ou sommet). Viser au moins {ANNEES_MIN} ans."
        )
    else:
        statut, texte = "alerte", (
            f"{annees:.1f} ans : la droite ne capte qu'un moment de marché, elle ne vaut rien."
        )
    return _verification("historique", "Durée d'historique", statut, texte, annees=round(annees, 1))


def per_annuels(cloture: pd.Series, fondamentaux: list[dict]) -> dict[int, float]:
    """PER de chaque annee : cours moyen de l'annee / BPA de l'annee (BPA positif seulement)."""
    moyennes = cloture.groupby(cloture.index.year).mean()
    return {
        f["annee"]: float(moyennes[f["annee"]] / f["bpa"])
        for f in fondamentaux
        if f.get("bpa") and f["bpa"] > 0 and f["annee"] in moyennes.index
    }


def _croissance(annees: list[int], valeurs: list[float]) -> float:
    """Croissance annuelle moyenne par regression de ln(valeur) sur l'annee (robuste au yo-yo)."""
    pente, _ = np.polyfit(np.array(annees, dtype=float), np.log(valeurs), 1)
    return float(np.exp(pente) - 1)


def per(reg: Regression, cloture: pd.Series, fondamentaux: list[dict]) -> dict:
    titre = "Pente portée par les bénéfices"
    debut, fin = reg.debut.year, reg.fin.year
    bpa = sorted(
        (f["annee"], f["bpa"]) for f in fondamentaux
        if f.get("bpa") and f["bpa"] > 0 and debut <= f["annee"] <= fin
    )
    if len(bpa) < 3:
        return _verification(
            "per", titre, "inconnu",
            "Pas assez de BPA positifs dans la période (3 années minimum). "
            "Importez l'historique des bénéfices par action pour valider la pente.",
            annees_bpa=len(bpa),
        )

    annees = [a for a, _ in bpa]
    pers = per_annuels(cloture, fondamentaux)
    croissance_bpa = _croissance(annees, [v for _, v in bpa])
    derive_per = _croissance(annees, [pers[a] for a in annees])

    # Pente du cours seul (hors dividendes) sur les memes annees : cours = BPA x PER.
    fenetre = cloture[(cloture.index.year >= annees[0]) & (cloture.index.year <= annees[-1])]
    reg_prix = ajuster(fenetre)
    pente_prix = reg_prix.pente if reg_prix else None

    per_actuel = float(cloture.iloc[-1] / bpa[-1][1])
    per_median = float(np.median(list(pers.values())))
    etendue = annees[-1] - annees[0] + 1

    sens = "gonflé" if derive_per > 0 else "comprimé"
    if abs(derive_per) < 0.02:
        statut = "ok"
        texte = (f"BPA en croissance de {croissance_bpa:+.1%}/an, PER stable "
                 f"({derive_per:+.1%}/an) : la pente reflète l'économie de l'entreprise.")
    elif abs(derive_per) < 0.05:
        statut = "attention"
        texte = (f"Le PER s'est {sens} de {derive_per:+.1%}/an pendant que le BPA progressait de "
                 f"{croissance_bpa:+.1%}/an : une partie de la pente vient de l'humeur du marché.")
    else:
        statut = "alerte"
        if derive_per > 0:
            texte = (f"Pente dopée par le PER ({derive_per:+.1%}/an) bien plus que par le BPA "
                     f"({croissance_bpa:+.1%}/an). Une renotation ne se répète pas : "
                     f"la pente future se rapprochera de la croissance des bénéfices.")
        else:
            texte = (f"PER comprimé ({derive_per:+.1%}/an) alors que le BPA progresse de "
                     f"{croissance_bpa:+.1%}/an : méfiance du marché, ou belle entreprise "
                     f"mal-aimée ? À creuser.")
    if etendue < 10:
        # Sur quelques annees, le PER fait surtout du yo-yo : indice, pas verdict.
        statut = "attention"
        texte += f" Mesuré sur {etendue} ans seulement : importez un historique plus long pour conclure."

    return _verification(
        "per", titre, statut, texte,
        croissance_bpa=croissance_bpa, derive_per=derive_per, pente_prix=pente_prix,
        per_actuel=per_actuel, per_median=per_median, annees=etendue,
    )


def rupture(reg: Regression, cours: pd.Series, signalee: bool) -> dict:
    titre = "Entreprise fidèle à elle-même"
    if signalee:
        return _verification(
            "rupture", titre, "alerte",
            "Rupture signalée : la droite décrit l'ancienne entreprise, "
            "elle n'est plus significative pour juger l'avenir.",
            signalee=True,
        )

    recent = cours[cours.index >= reg.fin - pd.DateOffset(years=ANNEES_RECENTES)]
    reg_recente = ajuster(recent)
    if reg_recente is None or (reg.fin - reg.debut).days < 2 * ANNEES_RECENTES * 365:
        return _verification("rupture", titre, "inconnu",
                             "Historique trop court pour comparer la pente récente.", signalee=False)

    ecart = reg_recente.pente - reg.pente
    details = {"signalee": False, "pente_recente": reg_recente.pente, "ecart": ecart}
    if abs(ecart) > max(0.08, abs(reg.pente)):
        return _verification(
            "rupture", titre, "attention",
            f"Pente des {ANNEES_RECENTES} dernières années ({reg_recente.pente:+.1%}/an) très "
            f"différente de la pente longue ({reg.pente:+.1%}/an). Simple cycle, ou changement "
            f"de nature ? Vérifiez les comptes et la stratégie.",
            **details,
        )
    return _verification(
        "rupture", titre, "ok",
        f"Pente récente ({reg_recente.pente:+.1%}/an) cohérente avec la pente longue. "
        f"Les ruptures sont rares — à confirmer par les comptes.",
        **details,
    )


def verdict(verifications: list[dict]) -> dict:
    pire = max(verifications, key=lambda v: ORDRE[v["statut"]])["statut"]
    textes = {
        "ok":        "Les trois conditions sont réunies : la droite est un guide fiable.",
        "inconnu":   "Droite exploitable, mais au moins une vérification manque de données.",
        "attention": "Droite à utiliser avec prudence : un point mérite d'être creusé.",
        "alerte":    "Droite trompeuse en l'état : ne pas la prolonger telle quelle.",
    }
    return {"statut": pire, "texte": textes[pire]}
