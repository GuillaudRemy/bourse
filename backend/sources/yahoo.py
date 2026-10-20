"""Acces aux donnees de Yahoo Finance via yfinance (bibliotheque libre, sans cle d'API).

Couverture : actions, indices et ETF du monde entier, cours quotidiens depuis
l'introduction en bourse, dividendes et divisions complets. Les comptes annuels ne
remontent en revanche que sur 4 a 5 ans : SEC, ESEF et les imports prennent le relais.

Les chiffres par action de Yahoo sont deja ajustes des divisions d'actions.
"""
import math
from dataclasses import dataclass
from datetime import date

import pandas as pd
import yfinance as yf

from backend.sources.base import Comptes, Identite, SourceIndisponible
from backend.sources.reseau import avec_tentatives

__all__ = ["SourceIndisponible", "Fiche", "rechercher", "fiche", "cours", "comptes", "divisions"]

NOM = "yahoo"

# Ratios gardes de `Ticker.info`, sous un nom francais.
INFOS = {
    "per":                "trailingPE",
    "per_previsionnel":   "forwardPE",
    "bpa":                "trailingEps",
    "capitalisation":     "marketCap",
    "valeur_entreprise":  "enterpriseValue",
    "rendement":          "dividendYield",      # deja en pourcentage
    "cours_valeur_comptable": "priceToBook",
    "roe":                "returnOnEquity",
    "marge_nette":        "profitMargins",
    "dette_capitaux":     "debtToEquity",
    "beta":               "beta",
    "industrie":          "industry",
    "actions_en_circulation": "sharesOutstanding",
}

TYPES = {"EQUITY": "action", "INDEX": "indice", "ETF": "etf", "MUTUALFUND": "etf"}

# Poste (champs.py) -> lignes Yahoo candidates, par etat financier.
LIGNES_RESULTAT = {
    "chiffre_affaires": ("Total Revenue", "Operating Revenue"),
    "marge_brute":      ("Gross Profit",),
    "frais_generaux":   ("Selling General And Administration",),
    "ebitda":           ("EBITDA", "Normalized EBITDA"),
    "amortissements":   ("Reconciled Depreciation", "Depreciation And Amortization In Income Statement"),
    "ebit":             ("EBIT", "Operating Income"),
    "charges_interets": ("Interest Expense", "Interest Expense Non Operating"),
    "benefice_net":     ("Net Income Common Stockholders", "Net Income"),
    "bpa":              ("Diluted EPS", "Basic EPS"),
    "nombre_actions":   ("Diluted Average Shares", "Basic Average Shares"),
}
LIGNES_BILAN = {
    "total_actif":                 ("Total Assets",),
    "actifs_courants":             ("Current Assets",),
    "tresorerie":                  ("Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"),
    "creances_clients":            ("Accounts Receivable", "Receivables"),
    "immobilisations_corporelles": ("Net PPE",),
    "goodwill":                    ("Goodwill",),
    "passifs_courants":            ("Current Liabilities",),
    "total_passif":                ("Total Liabilities Net Minority Interest",),
    "dette_financiere":            ("Total Debt",),
    "dette_long_terme":            ("Long Term Debt", "Long Term Debt And Capital Lease Obligation"),
    "capitaux_propres":            ("Stockholders Equity", "Common Stock Equity"),
    "resultats_non_distribues":    ("Retained Earnings",),
}
LIGNES_FLUX = {
    "flux_operationnel": ("Operating Cash Flow",),
    "capex":             ("Capital Expenditure", "Purchase Of PPE"),
    "dividendes_verses": ("Cash Dividends Paid", "Common Stock Dividend Paid"),
    "rachats_actions":   ("Repurchase Of Capital Stock", "Common Stock Payments"),
}
# Depenses publiees en negatif par Yahoo, stockees en positif.
DEPENSES = {"capex", "dividendes_verses", "rachats_actions", "charges_interets"}


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
    devise_comptes: str | None = None


def rechercher(texte: str, nombre: int = 8) -> list[dict]:
    """Par nom, symbole ou ISIN."""
    try:
        resultats = avec_tentatives(lambda: yf.Search(texte, max_results=nombre, news_count=0).quotes)
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
        info = avec_tentatives(lambda: yf.Ticker(symbole).info or {}, tentatives=2)
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
        devise_comptes=info.get("financialCurrency"),
    )


def cours(symbole: str, debut: date | None = None) -> pd.DataFrame:
    """Cours quotidiens. Colonnes : jour, ouverture, haut, bas, cloture, ajuste, volume.

    `ajuste` (Adj Close) integre dividendes et divisions : c'est le rendement total.
    """
    try:
        historique = avec_tentatives(lambda: yf.Ticker(symbole).history(
            start=debut.isoformat() if debut else None,
            period=None if debut else "max",
            auto_adjust=False,
            actions=False,
        ))
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


def divisions(symbole: str) -> list[tuple[date, float]]:
    """Divisions d'actions et attributions gratuites : (jour, nouvelles actions pour une)."""
    try:
        serie = avec_tentatives(lambda: yf.Ticker(symbole).splits)
    except Exception as e:
        raise SourceIndisponible(f"Divisions Yahoo de {symbole} indisponibles : {e}") from e
    if serie is None or serie.empty:
        return []
    return [(jour.date(), float(ratio)) for jour, ratio in serie.items() if ratio and ratio > 0 and ratio != 1]


def comptes(identite: Identite) -> Comptes:
    """Trois etats financiers (4-5 dernieres annees) et dividende par action (tout l'historique)."""
    ticker = yf.Ticker(identite.symbole)
    annees: Comptes = {}

    for attribut, lignes in (("income_stmt", LIGNES_RESULTAT), ("balance_sheet", LIGNES_BILAN),
                             ("cashflow", LIGNES_FLUX)):
        try:
            etat = avec_tentatives(lambda a=attribut: getattr(ticker, a), tentatives=2)
        except Exception:
            continue
        if etat is None or etat.empty:
            continue
        for colonne in etat.columns:
            annee = pd.Timestamp(colonne).year      # annee de cloture de l'exercice
            for cle, candidats in lignes.items():
                for nom in candidats:
                    if nom in etat.index and (v := _propre(etat.at[nom, colonne])) is not None:
                        annees.setdefault(annee, {})[cle] = abs(v) if cle in DEPENSES else v
                        break

    try:
        dividendes = avec_tentatives(lambda: ticker.dividends, tentatives=2)
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
