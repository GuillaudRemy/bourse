"""Outils communs aux comptes au format XBRL (SEC aux Etats-Unis, ESEF en Europe).

Les deux publient les comptes « tels que declares » : les chiffres par action sont
ramenes a la base d'actions actuelle en tenant compte des divisions survenues APRES
la publication du rapport (un rapport integre deja les divisions anterieures).
"""
from datetime import date, timedelta

from backend.db.champs import PAR_ACTION_CLES

# Concepts IFRS (taxonomie ifrs-full) candidats pour chaque poste, par ordre de preference.
IFRS = {
    "chiffre_affaires": ["Revenue", "RevenueFromContractsWithCustomers"],
    "marge_brute": ["GrossProfit"],
    "frais_generaux": ["SellingGeneralAndAdministrativeExpense"],
    "ebit": ["ProfitLossFromOperatingActivities"],
    "amortissements": ["DepreciationAndAmortisationExpense",
                       "DepreciationAmortisationAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss"],
    "charges_interets": ["InterestExpense", "FinanceCosts"],
    "benefice_net": ["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"],
    "bpa": ["DilutedEarningsLossPerShare", "BasicEarningsLossPerShare",
            "DilutedEarningsLossPerShareFromContinuingOperations"],
    "nombre_actions": ["AdjustedWeightedAverageShares", "WeightedAverageShares"],
    "dividende": ["DividendsRecognisedAsDistributionsToOwnersPerShare"],
    "total_actif": ["Assets"],
    "actifs_courants": ["CurrentAssets",
                        "CurrentAssetsOtherThanAssetsOrDisposalGroupsClassifiedAsHeldForSaleOrAsHeldForDistributionToOwners"],
    "tresorerie": ["CashAndCashEquivalents"],
    "creances_clients": ["TradeAndOtherCurrentReceivables", "CurrentTradeReceivables"],
    "immobilisations_corporelles": ["PropertyPlantAndEquipment"],
    "goodwill": ["Goodwill"],
    "passifs_courants": ["CurrentLiabilities",
                         "CurrentLiabilitiesOtherThanLiabilitiesIncludedInDisposalGroupsClassifiedAsHeldForSale"],
    "total_passif": ["Liabilities"],
    "dette_financiere": ["Borrowings"],
    "dette_long_terme": ["LongtermBorrowings", "NoncurrentPortionOfNoncurrentBorrowings"],
    "capitaux_propres": ["EquityAttributableToOwnersOfParent", "Equity"],
    "resultats_non_distribues": ["RetainedEarnings"],
    "flux_operationnel": ["CashFlowsFromUsedInOperatingActivities"],
    "capex": ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
              "PurchaseOfPropertyPlantAndEquipment"],
    "dividendes_verses": ["DividendsPaidToEquityHoldersOfParentClassifiedAsFinancingActivities",
                          "DividendsPaidClassifiedAsFinancingActivities", "DividendsPaid"],
    "rachats_actions": ["PaymentsToAcquireOrRedeemEntitysShares"],
}

# Postes reconstitues quand la societe ne publie pas le total.
SOMMES = {
    "dette_financiere": ["LongtermBorrowings", "CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings"],
    "total_passif": ["NoncurrentLiabilities", "CurrentLiabilities"],
}

DEPENSES = {"capex", "dividendes_verses", "rachats_actions", "charges_interets"}
DELAI_PUBLICATION = timedelta(days=90)   # un rapport annuel sort ~3 mois apres la cloture


def facteur_divisions(divisions: list[tuple[date, float]], apres: date) -> float:
    """Produit des ratios des divisions survenues apres `apres`."""
    facteur = 1.0
    for jour, ratio in divisions:
        if jour > apres:
            facteur *= ratio
    return facteur


def ajuster_divisions(valeurs: dict[str, float], facteur: float) -> dict[str, float]:
    """Ramene les postes par action (et le nombre d'actions) a la base d'actions actuelle."""
    if facteur == 1:
        return valeurs
    resultat = dict(valeurs)
    for cle in PAR_ACTION_CLES:
        if resultat.get(cle) is not None:
            resultat[cle] = resultat[cle] / facteur
    if resultat.get("nombre_actions") is not None:
        resultat["nombre_actions"] = resultat["nombre_actions"] * facteur
    return resultat


def signe(cle: str, valeur: float) -> float:
    return abs(valeur) if cle in DEPENSES else valeur
