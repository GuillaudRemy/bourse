"""Acces aux donnees de Yahoo Finance via yfinance (bibliotheque libre, sans cle d'API).

Couverture : actions, indices et ETF du monde entier, cours quotidiens depuis
l'introduction en bourse, dividendes et divisions complets. Les comptes annuels ne
remontent en revanche que sur 4 a 5 ans : SEC, ESEF et les imports prennent le relais.

Les chiffres par action de Yahoo sont deja ajustes des divisions d'actions.
"""
import json
import math
from dataclasses import dataclass
from datetime import date

import pandas as pd
import yfinance as yf

from backend.core import brut
from backend.sources.base import Comptes, Identite, SourceIndisponible
from backend.sources.reseau import avec_tentatives

__all__ = ["SourceIndisponible", "Fiche", "rechercher", "fiche", "cours", "comptes", "divisions", "evenements"]

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

TYPES = {"EQUITY": "action", "INDEX": "indice", "ETF": "etf", "MUTUALFUND": "etf", "FUTURE": "matiere",
         "CURRENCY": "devise", "CRYPTOCURRENCY": "crypto"}

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
    brut.conserver("yahoo", f"fiche-{symbole}.json", json.dumps(info, default=str).encode())
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


def cours_et_divisions(symbole: str) -> tuple[pd.DataFrame, list[tuple[date, float]]]:
    """Cours et divisions en UN seul appel (l'historique contient deja les divisions) :
    deux fois moins de requetes lors de l'actualisation quotidienne."""
    try:
        historique = avec_tentatives(lambda: yf.Ticker(symbole).history(period="max", auto_adjust=False, actions=True))
    except Exception as e:
        raise SourceIndisponible(f"Cours Yahoo de {symbole} indisponibles : {e}") from e
    brut.conserver("yahoo", f"cours-{symbole}.csv", historique.to_csv().encode())
    if historique.empty:
        return pd.DataFrame(), []
    divisions_ = []
    if "Stock Splits" in historique.columns:
        divisions_ = [(jour.date(), float(r)) for jour, r in historique["Stock Splits"].items() if r and r > 0 and r != 1]
    df = historique.rename(columns={
        "Open": "ouverture", "High": "haut", "Low": "bas",
        "Close": "cloture", "Adj Close": "ajuste", "Volume": "volume", "Dividends": "dividende",
    })
    df["jour"] = [d.date() for d in df.index]
    if "dividende" not in df.columns:
        df["dividende"] = 0.0
    df = df[["jour", "ouverture", "haut", "bas", "cloture", "ajuste", "volume", "dividende"]]
    return df.dropna(subset=["cloture"]).reset_index(drop=True), divisions_


def cours_recents(symbole: str, debut: date) -> tuple[pd.DataFrame, bool]:
    """Seances depuis `debut` seulement (actualisation rapide), et vrai si un dividende ou une
    division tombe dans la periode : le cours ajuste de TOUT le passe change alors, il faut
    retelecharger l'historique complet."""
    try:
        historique = avec_tentatives(lambda: yf.Ticker(symbole).history(start=debut.isoformat(), auto_adjust=False,
                                                                          actions=True))
    except Exception as e:
        raise SourceIndisponible(f"Cours Yahoo de {symbole} indisponibles : {e}") from e
    brut.conserver("yahoo", f"cours-recents-{symbole}.csv", historique.to_csv().encode())
    if historique.empty:
        return pd.DataFrame(), False
    evenement = any((historique[c].fillna(0) != 0).any() for c in ("Dividends", "Stock Splits") if c in historique.columns)
    df = historique.rename(columns={
        "Open": "ouverture", "High": "haut", "Low": "bas",
        "Close": "cloture", "Adj Close": "ajuste", "Volume": "volume",
    })
    df["jour"] = [d.date() for d in df.index]
    df = df[["jour", "ouverture", "haut", "bas", "cloture", "ajuste", "volume"]]
    return df.dropna(subset=["cloture"]).reset_index(drop=True), evenement


def divisions(symbole: str) -> list[tuple[date, float]]:
    """Divisions d'actions et attributions gratuites : (jour, nouvelles actions pour une)."""
    try:
        serie = avec_tentatives(lambda: yf.Ticker(symbole).splits)
    except Exception as e:
        raise SourceIndisponible(f"Divisions Yahoo de {symbole} indisponibles : {e}") from e
    if serie is None or serie.empty:
        return []
    return [(jour.date(), float(ratio)) for jour, ratio in serie.items() if ratio and ratio > 0 and ratio != 1]


def evenements(symbole: str) -> list[tuple[date, str, str | None]]:
    """Prochaines dates (resultats, dividende) et detachements des trois dernieres annees."""
    ticker = yf.Ticker(symbole)
    resultat: list[tuple[date, str, str | None]] = []
    try:
        calendrier = avec_tentatives(lambda: ticker.calendar, tentatives=2) or {}
    except Exception:
        calendrier = {}
    for jour in calendrier.get("Earnings Date") or []:
        if isinstance(jour, date):
            resultat.append((jour, "resultats", "Publication des résultats"))
    if isinstance(calendrier.get("Ex-Dividend Date"), date):
        resultat.append((calendrier["Ex-Dividend Date"], "detachement", "Détachement du dividende"))
    if isinstance(calendrier.get("Dividend Date"), date):
        resultat.append((calendrier["Dividend Date"], "paiement", "Paiement du dividende"))
    try:
        dividendes = avec_tentatives(lambda: ticker.dividends, tentatives=2)
    except Exception:
        dividendes = pd.Series(dtype=float)
    if dividendes is not None and not dividendes.empty:
        # yfinance renvoie parfois des lignes parasites (« Dividends » en guise de date, vu sur
        # ArcelorMittal) : on ne garde que les lignes lisibles, sans faire echouer la valeur.
        lisibles = []
        for jour, montant in dividendes.items():
            try:
                lisibles.append((pd.Timestamp(jour).date(), float(montant)))
            except (ValueError, TypeError):
                continue
        if lisibles:
            limite = max(j for j, _ in lisibles) - pd.DateOffset(years=3)
            for jour, montant in lisibles:
                if pd.Timestamp(jour) >= limite:
                    resultat.append((jour, "detachement", f"Dividende de {montant:.2f}".replace(".", ",")))
    return resultat


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


def consensus(symbole: str) -> dict | None:
    """Previsions des analystes : BPA de l'exercice en cours (« 0y ») et du suivant (« +1y »),
    leur evolution sur 90 jours, les revisions, l'objectif de cours et les recommandations.
    None si Yahoo n'a aucune prevision pour cette valeur."""
    ticker = yf.Ticker(symbole)
    try:
        estimations = avec_tentatives(lambda: ticker.earnings_estimate, tentatives=2)
        tendance = avec_tentatives(lambda: ticker.eps_trend, tentatives=2)
        revisions = avec_tentatives(lambda: ticker.eps_revisions, tentatives=2)
        objectifs = avec_tentatives(lambda: ticker.analyst_price_targets, tentatives=2) or {}
        recommandations = avec_tentatives(lambda: ticker.recommendations_summary, tentatives=2)
    except Exception as e:
        raise SourceIndisponible(f"Consensus indisponible : {e}") from e

    def ligne(df, periode, colonne):
        if df is None or df.empty or periode not in df.index or colonne not in df.columns:
            return None
        return _propre(df.loc[periode, colonne])

    exercices = []
    for periode, decalage in (("0y", 0), ("+1y", 1)):
        bpa = ligne(estimations, periode, "avg")
        if bpa is None:
            continue
        il_y_a_90_jours = ligne(tendance, periode, "90daysAgo")
        exercices.append({
            "decalage": decalage, "bpa": bpa,
            "bas": ligne(estimations, periode, "low"), "haut": ligne(estimations, periode, "high"),
            "analystes": ligne(estimations, periode, "numberOfAnalysts"),
            "croissance": ligne(estimations, periode, "growth"),
            "bpa_annee_precedente": ligne(estimations, periode, "yearAgoEps"),
            "evolution_90j": bpa / il_y_a_90_jours - 1 if il_y_a_90_jours else None,
            "hausses_30j": ligne(revisions, periode, "upLast30days"),
            "baisses_30j": ligne(revisions, periode, "downLast30days"),
        })
    avis = None
    if recommandations is not None and not recommandations.empty:
        derniere = recommandations.iloc[0]
        avis = {k: int(derniere.get(k) or 0) for k in ("strongBuy", "buy", "hold", "sell", "strongSell")}
    objectif = {k: _propre(objectifs.get(k)) for k in ("mean", "median", "low", "high", "current")}
    if not exercices and not avis and objectif.get("mean") is None:
        return None
    devise = None
    if estimations is not None and "currency" in getattr(estimations, "columns", []):
        devise = next((d for d in estimations["currency"] if isinstance(d, str)), None)
    return {"exercices": exercices, "objectif": objectif, "recommandations": avis, "devise": devise}
