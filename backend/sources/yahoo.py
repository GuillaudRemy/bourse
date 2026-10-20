"""Acces aux donnees de Yahoo Finance via yfinance (bibliotheque libre, sans cle d'API).

Couverture : actions, indices et ETF du monde entier, cours quotidiens depuis
l'introduction en bourse, dividendes complets. Les comptes annuels ne remontent
en revanche que sur 4 a 5 ans : pour un historique plus long, on les importe.
"""
import math
from dataclasses import dataclass
from datetime import date

import pandas as pd
import yfinance as yf

# Ratios gardes de `Ticker.info`, sous un nom francais.
INFOS = {
    "per":                "trailingPE",
    "per_previsionnel":   "forwardPE",
    "bpa":                "trailingEps",
    "capitalisation":     "marketCap",
    "rendement":          "dividendYield",      # deja en pourcentage
    "cours_valeur_comptable": "priceToBook",
    "roe":                "returnOnEquity",
    "marge_nette":        "profitMargins",
    "dette_capitaux":     "debtToEquity",
    "beta":               "beta",
    "industrie":          "industry",
}

TYPES = {"EQUITY": "action", "INDEX": "indice", "ETF": "etf", "MUTUALFUND": "etf"}


class SourceIndisponible(Exception):
    """Yahoo ne repond pas, ou ne connait pas le symbole."""


@dataclass
class Fiche:
    symbole: str
    nom:     str
    type:    str
    devise:  str | None
    place:   str | None
    secteur: str | None
    pays:    str | None
    infos:   dict


def rechercher(texte: str, nombre: int = 8) -> list[dict]:
    try:
        resultats = yf.Search(texte, max_results=nombre, news_count=0).quotes
    except Exception as e:  # reseau, format inattendu…
        raise SourceIndisponible(f"Recherche Yahoo impossible : {e}") from e

    return [
        {
            "symbole": q["symbol"],
            "nom":     q.get("longname") or q.get("shortname") or q["symbol"],
            "type":    TYPES.get(q.get("quoteType", ""), "action"),
            "place":   q.get("exchDisp") or q.get("exchange"),
            "secteur": q.get("sector"),
        }
        for q in resultats
        if q.get("symbol") and q.get("quoteType") in TYPES
    ]


def fiche(symbole: str) -> Fiche:
    try:
        info = yf.Ticker(symbole).info or {}
    except Exception as e:
        raise SourceIndisponible(f"Fiche Yahoo de {symbole} indisponible : {e}") from e
    if not info.get("quoteType"):
        raise SourceIndisponible(f"Symbole inconnu de Yahoo : {symbole}")

    return Fiche(
        symbole=symbole,
        nom=info.get("longName") or info.get("shortName") or symbole,
        type=TYPES.get(info.get("quoteType", ""), "action"),
        devise=info.get("currency"),
        place=info.get("exchange"),
        secteur=info.get("sector"),
        pays=info.get("country"),
        infos={cle: _propre(info.get(nom)) for cle, nom in INFOS.items() if info.get(nom) is not None},
    )


def cours(symbole: str, debut: date | None = None) -> pd.DataFrame:
    """Cours quotidiens. Colonnes : jour, ouverture, haut, bas, cloture, ajuste, volume.

    `ajuste` (Adj Close) integre dividendes et divisions : c'est le rendement total.
    """
    try:
        historique = yf.Ticker(symbole).history(
            start=debut.isoformat() if debut else None,
            period=None if debut else "max",
            auto_adjust=False,
            actions=False,
        )
    except Exception as e:
        raise SourceIndisponible(f"Cours Yahoo de {symbole} indisponibles : {e}") from e
    if historique.empty:
        return pd.DataFrame()

    df = historique.rename(columns={
        "Open": "ouverture", "High": "haut", "Low": "bas",
        "Close": "cloture", "Adj Close": "ajuste", "Volume": "volume",
    })
    df["jour"] = [d.date() for d in df.index]   # date locale de la place de cotation
    df = df[["jour", "ouverture", "haut", "bas", "cloture", "ajuste", "volume"]]
    return df.dropna(subset=["cloture"]).reset_index(drop=True)


def fondamentaux(symbole: str) -> dict[int, dict]:
    """Par annee : bpa, benefice_net, chiffre_affaires (4-5 ans) et dividende (tout l'historique)."""
    ticker = yf.Ticker(symbole)
    annees: dict[int, dict] = {}

    try:
        compte = ticker.income_stmt
    except Exception:
        compte = pd.DataFrame()
    lignes = {
        "bpa":              ("Diluted EPS", "Basic EPS"),
        "benefice_net":     ("Net Income", "Net Income Common Stockholders"),
        "chiffre_affaires": ("Total Revenue", "Operating Revenue"),
    }
    if compte is not None and not compte.empty:
        for colonne in compte.columns:
            annee = pd.Timestamp(colonne).year
            for cle, candidats in lignes.items():
                for nom in candidats:
                    if nom in compte.index and _propre(compte.at[nom, colonne]) is not None:
                        annees.setdefault(annee, {})[cle] = _propre(compte.at[nom, colonne])
                        break

    try:
        dividendes = ticker.dividends
    except Exception:
        dividendes = pd.Series(dtype=float)
    if dividendes is not None and not dividendes.empty:
        par_annee = dividendes.groupby(dividendes.index.year).sum()
        for annee, montant in par_annee.items():
            # L'annee en cours est incomplete : on ne la retient pas.
            if annee < date.today().year:
                annees.setdefault(int(annee), {})["dividende"] = round(float(montant), 4)

    return annees


def _propre(valeur):
    """NaN et infinis deviennent None ; les types numpy deviennent natifs."""
    if valeur is None or isinstance(valeur, str):
        return valeur
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(nombre) or math.isinf(nombre) else nombre
