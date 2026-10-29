"""Catalogue des marches suivis sans recherche : matieres premieres, devises, taux, obligations, cryptomonnaies.

Chaque famille s'ajoute en un clic, avec un nom francais et le bon type (Yahoo classe par exemple
le taux americain a 10 ans parmi les indices, et nomme l'or par son echeance « Gold Dec 26 »).

Les taux europeens ne sont pas chez Yahoo : ils viennent de la BCE (source « bce »), quotidiens
pour la courbe de la zone euro et le taux de depot, mensuels pour les emprunts d'Etat par pays.
"""
from typing import NamedTuple


class Entree(NamedTuple):
    symbole: str
    nom: str
    detail: str                   # unite, ou ce que represente le chiffre
    source: str = "yahoo"
    serie: str | None = None      # cle de la serie BCE (source « bce »)


MATIERES = [
    # Contrats a terme en continu chez Yahoo (symboles « =F »), historique quotidien depuis 2000 environ.
    Entree("GC=F", "Or", "once troy"),
    Entree("SI=F", "Argent", "once troy"),
    Entree("PL=F", "Platine", "once troy"),
    Entree("PA=F", "Palladium", "once troy"),
    Entree("HG=F", "Cuivre", "livre"),
    Entree("BZ=F", "Pétrole Brent", "baril"),
    Entree("CL=F", "Pétrole WTI", "baril"),
    Entree("NG=F", "Gaz naturel Henry Hub", "MMBtu"),
    Entree("ZW=F", "Blé de Chicago", "boisseau"),
    Entree("ZC=F", "Maïs", "boisseau"),
    Entree("KC=F", "Café arabica", "livre"),
    Entree("CC=F", "Cacao", "tonne"),
    Entree("SB=F", "Sucre", "livre"),
]
DEVISES = [
    # Cours de reference : unites de la seconde devise pour 1 unite de la premiere.
    Entree("EURUSD=X", "Euro / Dollar américain", "dollars pour 1 euro"),
    Entree("EURGBP=X", "Euro / Livre sterling", "livres pour 1 euro"),
    Entree("EURCHF=X", "Euro / Franc suisse", "francs suisses pour 1 euro"),
    Entree("EURJPY=X", "Euro / Yen", "yens pour 1 euro"),
    Entree("EURCNY=X", "Euro / Yuan", "yuans pour 1 euro"),
    Entree("EURCAD=X", "Euro / Dollar canadien", "dollars canadiens pour 1 euro"),
    Entree("EURAUD=X", "Euro / Dollar australien", "dollars australiens pour 1 euro"),
    Entree("USDJPY=X", "Dollar américain / Yen", "yens pour 1 dollar"),
    Entree("USDCHF=X", "Dollar américain / Franc suisse", "francs suisses pour 1 dollar"),
]
TAUX = [
    Entree("TAUX-DEPOT-BCE", "Taux de dépôt de la BCE", "taux directeur, quotidien", "bce", "FM/D.U2.EUR.4F.KR.DFR.LEV"),
    Entree("TAUX-ZE-AAA-10A", "Taux à 10 ans des États de la zone euro notés AAA", "proche du Bund allemand, quotidien",
           "bce", "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y"),
    Entree("TAUX-ZE-10A", "Taux à 10 ans, ensemble de la zone euro", "tous les États, quotidien",
           "bce", "YC/B.U2.EUR.4F.G_N_C.SV_C_YM.SR_10Y"),
    Entree("TAUX-FR-10A", "OAT 10 ans (France)", "moyenne mensuelle", "bce", "IRS/M.FR.L.L40.CI.0000.EUR.N.Z"),
    Entree("TAUX-DE-10A", "Bund 10 ans (Allemagne)", "moyenne mensuelle", "bce", "IRS/M.DE.L.L40.CI.0000.EUR.N.Z"),
    Entree("TAUX-IT-10A", "BTP 10 ans (Italie)", "moyenne mensuelle", "bce", "IRS/M.IT.L.L40.CI.0000.EUR.N.Z"),
    Entree("TAUX-ES-10A", "Bono 10 ans (Espagne)", "moyenne mensuelle", "bce", "IRS/M.ES.L.L40.CI.0000.EUR.N.Z"),
    Entree("^IRX", "Taux américain à 3 mois", "bons du Trésor, quotidien"),
    Entree("^FVX", "Taux américain à 5 ans", "quotidien"),
    Entree("^TNX", "Taux américain à 10 ans", "quotidien"),
    Entree("^TYX", "Taux américain à 30 ans", "quotidien"),
]
OBLIGATIONS = [
    # Pas d'obligations « en direct » gratuites : des ETF obligataires, qui se lisent comme un ETF.
    Entree("EUNH.DE", "Obligations d'État zone euro (iShares Core)", "toutes durées, en euros"),
    Entree("XGLE.DE", "Obligations d'État zone euro (Xtrackers)", "toutes durées, en euros"),
    Entree("IBGL.AS", "Obligations d'État zone euro 15-30 ans (iShares)", "longues durées, en euros"),
    Entree("EUN5.DE", "Obligations d'entreprises en euros (iShares Core)", "toutes durées, en euros"),
    Entree("EUNA.DE", "Obligations mondiales (iShares Core Global Aggregate)", "couvert en euros"),
    Entree("TLT", "Obligations d'État américaines 20 ans et plus (iShares)", "en dollars"),
]
CRYPTOS = [
    Entree("BTC-EUR", "Bitcoin", "en euros, depuis 2014"),
    Entree("ETH-EUR", "Ether", "en euros, depuis 2017"),
    Entree("SOL-EUR", "Solana", "en euros, depuis 2020"),
    Entree("XRP-EUR", "XRP", "en euros, depuis 2017"),
]
FAMILLES = {"matiere": MATIERES, "devise": DEVISES, "taux": TAUX, "obligation": OBLIGATIONS, "crypto": CRYPTOS}
PAR_SYMBOLE = {e.symbole: (type_, e) for type_, entrees in FAMILLES.items() for e in entrees}

# Pas de droite de regression : ni tendance de fond (devise), ni croissance (taux, parfois negatif).
SANS_DROITE = ("devise", "taux")

AVERTISSEMENTS = {
    "matiere": "Matière première : ni bénéfices ni dividendes. La droite décrit la tendance du prix (inflation, "
               "rareté), sans moteur de croissance comme une entreprise ; elle se lit avec prudence. Le prix suivi est "
               "celui du contrat à terme le plus proche, qui saute légèrement à chaque changement d'échéance.",
    "devise": "Taux de change : une devise n'a pas de tendance de fond durable, elle oscille au gré des taux d'intérêt, "
              "de l'inflation et des balances commerciales. Pas de droite de régression : l'analyse technique et la "
              "comparaison avec d'autres valeurs restent utiles.",
    "taux": "Taux d'intérêt, en % par an : pas de droite de régression (un taux ne croît pas comme une entreprise, et il "
            "a même été négatif en zone euro de 2015 à 2022). Les variations s'expriment en points. Quand les taux "
            "montent, le prix des obligations déjà émises baisse, et inversement.",
    "obligation": "ETF obligataire : un panier d'obligations, intérêts réinvestis. Son cours baisse quand les taux "
                  "montent, d'autant plus que ses obligations sont longues. La droite décrit le rendement moyen passé, "
                  "qui dépendait du niveau des taux de l'époque.",
    "crypto": "Cryptomonnaie : pas de bénéfices ni de dividendes, un historique court (depuis 2014 pour le bitcoin) et "
              "une volatilité extrême (des baisses de 70 à 80 % sont déjà survenues plusieurs fois). La droite résume "
              "un passé très court et ne dit rien d'un prix « normal » : à lire avec la plus grande prudence.",
}


def trouver(symbole: str) -> tuple[str, Entree] | None:
    """(type, entree) d'un symbole du catalogue, ou None."""
    return PAR_SYMBOLE.get(symbole.upper())


def nom(symbole: str) -> str | None:
    """Nom francais (avec l'unite pour une matiere premiere : « Or (once troy) »), ou None hors catalogue."""
    if not (trouve := trouver(symbole)):
        return None
    type_, e = trouve
    return f"{e.nom} ({e.detail})" if type_ == "matiere" else e.nom
