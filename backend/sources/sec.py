"""Comptes des societes cotees aux Etats-Unis : SEC EDGAR, API « companyfacts ».

Officiel, gratuit, sans cle : tous les chiffres XBRL des rapports 10-K depuis 2009 environ.
La SEC exige une adresse e-mail de contact dans chaque requete (reglage « contact_sec »).
"""
import time
from datetime import date

from backend.core import reglages
from backend.db.champs import PAR_ACTION_CLES
from backend.sources.base import Comptes, Identite, SourceIndisponible
from backend.sources.reseau import ErreurReseau, json_
from backend.sources.xbrl import IFRS, ajuster_divisions, facteur_divisions, signe

NOM = "sec"
URL_TICKERS = "https://www.sec.gov/files/company_tickers.json"
URL_FAITS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:0>10}.json"
FORMULAIRES = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}

# Concepts US GAAP candidats pour chaque poste, par ordre de preference.
US_GAAP = {
    "chiffre_affaires": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                         "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "marge_brute": ["GrossProfit"],
    "frais_generaux": ["SellingGeneralAndAdministrativeExpense"],
    "ebit": ["OperatingIncomeLoss"],
    "amortissements": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
                       "DepreciationAmortizationAndAccretionNet", "Depreciation"],
    "charges_interets": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
    "benefice_net": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "bpa": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
    "nombre_actions": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "dividende": ["CommonStockDividendsPerShareCashPaid", "CommonStockDividendsPerShareDeclared"],
    "total_actif": ["Assets"],
    "actifs_courants": ["AssetsCurrent"],
    "tresorerie": ["CashAndCashEquivalentsAtCarryingValue",
                   "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "creances_clients": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
    "immobilisations_corporelles": ["PropertyPlantAndEquipmentNet"],
    "goodwill": ["Goodwill"],
    "passifs_courants": ["LiabilitiesCurrent"],
    "total_passif": ["Liabilities"],
    "dette_long_terme": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "dette_financiere": ["DebtLongtermAndShorttermCombinedAmount", "LongTermDebt"],
    "capitaux_propres": ["StockholdersEquity"],
    "resultats_non_distribues": ["RetainedEarningsAccumulatedDeficit"],
    "flux_operationnel": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "dividendes_verses": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    "rachats_actions": ["PaymentsForRepurchaseOfCommonStock"],
}
INSTANTANES = {"total_actif", "actifs_courants", "tresorerie", "creances_clients", "immobilisations_corporelles",
               "goodwill", "passifs_courants", "total_passif", "dette_long_terme", "dette_financiere",
               "capitaux_propres", "resultats_non_distribues"}

_tickers: dict[str, str] = {}
_tickers_charges = 0.0


def _entetes() -> dict:
    contact = reglages.lire("contact_sec")
    if "@" not in contact:
        raise SourceIndisponible("SEC : renseignez votre e-mail de contact dans les Réglages.")
    return {"User-Agent": f"Bourse {contact}", "Accept-Encoding": "gzip, deflate"}


def _cik(symbole: str) -> str | None:
    global _tickers_charges
    if not _tickers or time.monotonic() - _tickers_charges > 86400:
        try:
            donnees = json_(URL_TICKERS, entetes=_entetes())
        except ErreurReseau as e:
            raise SourceIndisponible(f"SEC : {e}") from e
        _tickers.clear()
        _tickers.update({str(v["ticker"]).upper(): str(v["cik_str"]) for v in donnees.values()})
        _tickers_charges = time.monotonic()
    return _tickers.get(symbole.upper().replace(".", "-"))


def couvre(identite: Identite) -> bool:
    if identite.type != "action":
        return False
    if identite.cik:
        return True
    # Symbole Yahoo d'une place americaine : pas de suffixe de place (AAPL, BRK-B…).
    return "." not in identite.symbole and not identite.symbole.startswith("^")


def comptes(identite: Identite, divisions: list[tuple[date, float]] = ()) -> Comptes:
    cik = identite.cik or _cik(identite.symbole)
    if not cik:
        raise SourceIndisponible(f"SEC : {identite.symbole} n'est pas une société enregistrée auprès de la SEC.")
    identite.decouverts["cik"] = cik
    try:
        faits = json_(URL_FAITS.format(cik=cik), entetes=_entetes(), delai=(5, 60))["facts"]
    except ErreurReseau as e:
        raise SourceIndisponible(f"SEC : {e}") from e

    # Les emetteurs etrangers (20-F) publient en IFRS : meme logique, autre dictionnaire.
    taxonomie, concepts = ("us-gaap", US_GAAP) if "us-gaap" in faits else ("ifrs-full", IFRS)
    faits = faits.get(taxonomie, {})

    # 1. Exercices : fins des periodes annuelles du resultat net (ou du CA).
    fins: dict[str, int] = {}
    for concept in ("NetIncomeLoss", "ProfitLoss", "Revenues", "Revenue"):
        for e in _entrees(faits, concept):
            if _annuelle(e):
                fins[e["end"]] = date.fromisoformat(e["end"]).year
        if fins:
            break

    annees: Comptes = {}
    publie: dict[tuple[int, str], str] = {}   # date de publication de chaque chiffre retenu
    for cle, candidats in concepts.items():
        # Les societes changent de concept au fil des ans (Apple : SalesRevenueNet puis
        # RevenueFromContract… en 2018) : chaque annee prend le premier candidat qui la couvre.
        for concept in candidats:
            retenus: dict[int, dict] = {}
            for e in _entrees(faits, concept):
                if cle in INSTANTANES:
                    if e.get("start") or e["end"] not in fins:
                        continue
                elif not _annuelle(e):
                    continue
                annee = fins.get(e["end"], date.fromisoformat(e["end"]).year)
                # Plusieurs rapports citent la meme annee : le plus recent (chiffres retraites) l'emporte.
                if annee not in retenus or e["filed"] > retenus[annee]["filed"]:
                    retenus[annee] = e
            for annee, e in retenus.items():
                if cle not in annees.get(annee, {}):
                    annees.setdefault(annee, {})[cle] = signe(cle, float(e["val"]))
                    publie[annee, cle] = e["filed"]

    # Chaque chiffre par action est ajuste des divisions posterieures a SON rapport.
    for annee, valeurs in annees.items():
        for cle in [*PAR_ACTION_CLES, "nombre_actions"]:
            if cle in valeurs:
                facteur = facteur_divisions(list(divisions), date.fromisoformat(publie[annee, cle]))
                valeurs[cle] = ajuster_divisions({cle: valeurs[cle]}, facteur)[cle]
    return annees


def _entrees(faits: dict, concept: str) -> list[dict]:
    unites = faits.get(concept, {}).get("units", {})
    entrees = []
    for unite, liste in unites.items():
        if unite in ("USD", "USD/shares", "shares") or unite.isupper() or "/shares" in unite:
            entrees += [e for e in liste if e.get("form") in FORMULAIRES]
    return entrees


def _annuelle(e: dict) -> bool:
    if not e.get("start"):
        return False
    duree = (date.fromisoformat(e["end"]) - date.fromisoformat(e["start"])).days
    return 330 <= duree <= 400
