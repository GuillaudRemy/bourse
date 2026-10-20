"""Controle qualite d'une serie de cours, avant de lui faire confiance.

Une droite de regression tracee sur des donnees fausses est fausse : une division d'actions
mal ajustee cree une marche d'escalier, un cours a zero ecrase le logarithme, un trou de
plusieurs mois fausse la volatilite. On signale, on ne corrige pas : c'est a l'utilisateur
de decider (reimporter, couper l'historique avec la date de debut…).
"""
import numpy as np
import pandas as pd

TROU_JOURS = 10           # au-dela, on s'attend a des seances manquantes (hors longs feries)
SAUT = 0.40               # variation d'une seance consideree comme suspecte…
RETOUR = 0.25             # …si elle est en grande partie annulee a la seance suivante
FIGE_SEANCES = 20         # cours identique sur autant de seances d'affilee


def controler(cours: pd.DataFrame) -> dict:
    """Renvoie {"statut": ok|attention|alerte, "anomalies": [{type, gravite, texte, jour}]}."""
    anomalies: list[dict] = []
    cloture = cours["cloture"].dropna()
    if cloture.empty:
        return {"statut": "ok", "anomalies": []}

    nuls = cloture[cloture <= 0]
    if len(nuls):
        anomalies.append(_anomalie("zero", "alerte", f"{len(nuls)} cours nul(s) ou négatif(s)", nuls.index[0]))

    ecarts = cloture.index.to_series().diff().dt.days
    for jour, jours in ecarts[ecarts > TROU_JOURS].items():
        anomalies.append(_anomalie("trou", "attention" if jours < 60 else "alerte",
                                   f"Aucune cotation pendant {int(jours)} jours", jour))

    variation = cloture.pct_change()
    suivante = variation.shift(-1)
    for jour, v in variation[variation.abs() > SAUT].items():
        if pd.notna(suivante.get(jour)) and np.sign(suivante[jour]) != np.sign(v) and abs(suivante[jour]) > RETOUR:
            texte = f"Pic isolé de {v:+.0%} aussitôt annulé : probable erreur de cotation"
            anomalies.append(_anomalie("pic", "alerte", texte, jour))
        else:
            # Hausse ou baisse de ce type sur une seance : division mal ajustee ?
            ratio = 1 / (1 + v) if v < 0 else 1 + v
            texte = f"Variation de {v:+.0%} en une séance"
            if any(abs(ratio - r) < 0.05 * r for r in (2, 3, 4, 5, 10, 20)):
                texte += f" (≈ ×{round(ratio)} : division d'actions mal ajustée ?)"
            anomalies.append(_anomalie("saut", "attention", texte, jour))

    egal = (cloture.diff() == 0).astype(int)
    series = egal.groupby((egal == 0).cumsum()).cumsum()
    if series.max() >= FIGE_SEANCES:
        fin = series.idxmax()
        anomalies.append(_anomalie("fige", "attention", f"Cours identique pendant {int(series.max())} séances", fin))

    if "ajuste" in cours and cours["ajuste"].notna().any():
        rapport = (cours["ajuste"] / cours["cloture"]).dropna()
        if (rapport > 1.05).any():
            jour = rapport[rapport > 1.05].index[0]
            anomalies.append(_anomalie("ajuste", "attention",
                                       "Cours ajusté supérieur à la clôture : ajustement suspect", jour))

    gravites = {a["gravite"] for a in anomalies}
    statut = "alerte" if "alerte" in gravites else "attention" if gravites else "ok"
    return {"statut": statut, "anomalies": sorted(anomalies, key=lambda a: a["jour"])[-50:]}


def _anomalie(type_: str, gravite: str, texte: str, jour) -> dict:
    return {"type": type_, "gravite": gravite, "texte": texte, "jour": pd.Timestamp(jour).strftime("%Y-%m-%d")}
