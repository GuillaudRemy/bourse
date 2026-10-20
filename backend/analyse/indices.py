"""Indices « prix » et indices « dividendes reinvestis » (rendement total).

Un indice prix (CAC 40 ^FCHI, S&P 500 ^GSPC) ignore les dividendes : sur 30 ans, sa pente
sous-estime le rendement reel de 2 a 4 points par an. Pour la methode de la droite de
regression, il faut la version dividendes reinvestis (GR, TR, Net Return).
"""
import re

# Indice prix -> equivalent dividendes reinvestis disponible chez Yahoo.
EQUIVALENTS = {
    "^FCHI": ("PX1GR.PA", "CAC 40 GR"),
    "^GSPC": ("^SP500TR", "S&P 500 Total Return"),
    "^NDX": ("^NDXT", "Nasdaq-100 Total Return"),
}
# Indices deja dividendes reinvestis, par construction ou par leur nom.
RENDEMENT_TOTAL = {"PX1GR.PA", "^SP500TR", "^NDXT", "^GDAXI"}
MOTIF = re.compile(r"\b(GR|TR|NR|NETR|gross|net return|total return|rendement total)\b", re.IGNORECASE)


def avertissement(symbole: str, nom: str, type_: str) -> dict | None:
    """None si rien a signaler ; sinon {texte, symbole, nom} avec l'equivalent a suivre."""
    if type_ != "indice" or symbole.upper() in RENDEMENT_TOTAL or MOTIF.search(nom or ""):
        return None
    equivalent = EQUIVALENTS.get(symbole.upper())
    texte = ("Indice « prix » : il ne compte pas les dividendes, sa pente sous-estime le rendement réel "
             "de 2 à 4 points par an.")
    if equivalent:
        texte += f" Suivez plutôt {equivalent[1]} ({equivalent[0]})."
        return {"texte": texte, "symbole": equivalent[0], "nom": equivalent[1]}
    return {"texte": texte + " Cherchez sa version « GR », « TR » ou « Net Return ».", "symbole": None, "nom": None}
