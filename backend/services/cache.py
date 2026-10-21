"""Cache des fiches resumees (tableau de synthese, screener, comparaison).

Recalculer la regression, les ratios et la valorisation de 50 valeurs a chaque affichage
prendrait plusieurs secondes : chaque fiche est calculee une fois, puis gardee en memoire
jusqu'a ce que ses donnees changent (cours, comptes, reglages de la valeur). Toute ecriture
passe par `invalider`.
"""
import threading

_verrou = threading.Lock()
_fiches: dict[int, dict] = {}


def lire(valeur_id: int) -> dict | None:
    with _verrou:
        return _fiches.get(valeur_id)


def ecrire(valeur_id: int, fiche: dict) -> None:
    with _verrou:
        _fiches[valeur_id] = fiche


def invalider(valeur_id: int | None = None) -> None:
    """Une valeur, ou tout le cache (None : taux de change, reglage global…)."""
    with _verrou:
        if valeur_id is None:
            _fiches.clear()
        else:
            _fiches.pop(valeur_id, None)
