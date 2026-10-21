"""Frais d'un ordre de bourse : courtage du courtier et taxe sur les transactions financieres (TTF).

Courtage : max(minimum, fixe + pourcentage x montant), grille propre a chaque compte
(par defaut : reglages « frais_* »).

TTF (article 235 ter ZD du CGI) : due sur les ACHATS d'actions de societes dont le siege est en
France et dont la capitalisation depasse 1 milliard d'euros au 1er decembre de l'annee
precedente (121 societes en 2026). Hors champ : ventes, allers-retours dans la journee, ETF,
societes cotees a Paris mais au siege a l'etranger (Airbus, Stellantis…).
Taux : 0,2 % (aout 2012), 0,3 % (2017), 0,4 % depuis le 1er avril 2025 (loi de finances 2025).
On l'estime ici avec le pays et la capitalisation actuelle fournis par Yahoo.
"""
from datetime import date

TAUX_TTF = [(date(2025, 4, 1), 0.004), (date(2017, 1, 1), 0.003), (date(2012, 8, 1), 0.002)]
SEUIL_TTF = 1e9


def taux_ttf(jour: date) -> float:
    return next((taux for debut, taux in TAUX_TTF if jour >= debut), 0.0)


def assujetti_ttf(type_: str | None, pays: str | None, capitalisation: float | None) -> bool:
    return type_ == "action" and pays == "France" and (capitalisation or 0) >= SEUIL_TTF


def courtage(montant: float, fixe: float = 0.0, pct: float = 0.0, minimum: float = 0.0) -> float:
    return max(minimum, fixe + pct * abs(montant))


def ordre(montant: float, sens: str, jour: date, grille: dict, ttf_applicable: bool) -> dict:
    """Frais d'un achat ou d'une vente de `montant` euros."""
    c = courtage(montant, grille.get("fixe") or 0.0, grille.get("pct") or 0.0, grille.get("min") or 0.0)
    t = taux_ttf(jour) * abs(montant) if sens == "achat" and ttf_applicable else 0.0
    return {"courtage": round(c, 2), "ttf": round(t, 2), "total": round(c + t, 2), "taux_ttf": taux_ttf(jour)}
