"""Matieres premieres : prix de marche reels (contrats a terme en continu chez Yahoo, symboles « =F »).

Pas besoin d'ETF : Yahoo publie l'historique quotidien du contrat le plus proche depuis 2000
environ. Ses noms designent l'echeance (« Gold Dec 26 ») : on garde un nom francais et l'unite.

A savoir pour la lecture : une matiere premiere ne verse ni dividende ni benefice. Sa droite de
regression decrit la tendance du prix (inflation, rarete), sans moteur de croissance ; et le
« contrat en continu » saute legerement a chaque changement d'echeance.
"""

CATALOGUE = [
    # symbole, nom, unite
    ("GC=F", "Or", "once troy"),
    ("SI=F", "Argent", "once troy"),
    ("PL=F", "Platine", "once troy"),
    ("PA=F", "Palladium", "once troy"),
    ("HG=F", "Cuivre", "livre"),
    ("BZ=F", "Pétrole Brent", "baril"),
    ("CL=F", "Pétrole WTI", "baril"),
    ("NG=F", "Gaz naturel Henry Hub", "MMBtu"),
    ("ZW=F", "Blé de Chicago", "boisseau"),
    ("ZC=F", "Maïs", "boisseau"),
    ("KC=F", "Café arabica", "livre"),
    ("CC=F", "Cacao", "tonne"),
    ("SB=F", "Sucre", "livre"),
]
PAR_SYMBOLE = {s: (nom, unite) for s, nom, unite in CATALOGUE}


def nom(symbole: str) -> str | None:
    """Nom francais avec l'unite (« Or (once troy) »), ou None hors catalogue."""
    if symbole.upper() not in PAR_SYMBOLE:
        return None
    nom_, unite = PAR_SYMBOLE[symbole.upper()]
    return f"{nom_} ({unite})"


AVERTISSEMENT = ("Matière première : ni bénéfices ni dividendes. La droite décrit la tendance du prix (inflation, "
                 "rareté), sans moteur de croissance comme une entreprise ; elle se lit avec prudence. Le prix suivi est "
                 "celui du contrat à terme le plus proche, qui saute légèrement à chaque changement d'échéance.")
