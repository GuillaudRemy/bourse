"""Fiscalite francaise des placements en actions (particulier resident fiscal en France).

Sources (verifiees en octobre 2026) :
  · service-public.gouv.fr F21618 (plus-values de valeurs mobilieres) : PFU 31,4 % =
    12,8 % d'impot sur le revenu + 18,6 % de prelevements sociaux ; option possible pour le
    bareme progressif (prelevements sociaux toujours dus) ; moins-values imputables sur les
    plus-values de meme nature de l'annee, puis des 10 annees suivantes ;
  · service-public.gouv.fr F2385 (PEA, verifiee le 22/05/2026) : plafonds 150 000 € (PEA),
    225 000 € au total avec le PEA-PME ; apres 5 ans, gains exoneres d'impot sur le revenu mais
    prelevements sociaux dus ; avant 5 ans, un retrait cloture en principe le plan ;
  · LFSS 2026 : CSG sur les revenus du capital portee de 9,2 % a 10,6 % au 1er janvier 2026,
    soit des prelevements sociaux de 18,6 % (17,2 % auparavant).

Ce sont des ESTIMATIONS pour se reperer : l'IFU de l'etablissement et la declaration font foi.
"""
from collections import defaultdict

IMPOT_REVENU = 0.128
REPORT_MOINS_VALUES = 10             # annees
ABATTEMENT_DIVIDENDES = 0.40         # option pour le bareme uniquement
PLAFONDS = {"PEA": 150_000, "PEA-PME": 225_000}
PLAFOND_COMMUN = 225_000             # PEA + PEA-PME
ANCIENNETE_PEA = 5


def prelevements_sociaux(annee: int) -> float:
    return 0.186 if annee >= 2026 else 0.172


def pfu(annee: int) -> float:
    return IMPOT_REVENU + prelevements_sociaux(annee)


def compte_titres(ventes: list[tuple], dividendes: dict[int, float], tmi: float | None = None) -> list[dict]:
    """Par annee : plus-values, moins-values (avec report sur 10 ans), dividendes et impot estime.

    `ventes` : (jour, plus-value) ; `tmi` : tranche marginale d'imposition (0,11 ; 0,30…) pour
    estimer l'option pour le bareme."""
    par_annee: defaultdict[int, dict[str, float]] = defaultdict(lambda: {"plus_values": 0.0, "moins_values": 0.0})
    for jour, pv in ventes:
        par_annee[jour.year]["plus_values" if pv >= 0 else "moins_values"] += pv
    annees = sorted(set(par_annee) | set(dividendes))

    stock: list[list] = []          # [annee d'origine, montant reportable restant (positif)]
    resultat = []
    for annee in annees:
        stock = [s for s in stock if annee - s[0] <= REPORT_MOINS_VALUES and s[1] > 0]
        pv, mv = par_annee[annee]["plus_values"], -par_annee[annee]["moins_values"]
        net = pv - mv
        imputees = 0.0
        if net > 0:
            for s in stock:                      # les plus anciennes d'abord
                prise = min(s[1], net - imputees)
                s[1] -= prise
                imputees += prise
        elif net < 0:
            stock.append([annee, -net])
        base_pv = max(net - imputees, 0.0)
        div = dividendes.get(annee, 0.0)
        ps = prelevements_sociaux(annee)
        ligne = {
            "annee": annee, "plus_values": pv, "moins_values": -mv, "moins_values_anterieures_imputees": imputees,
            "dividendes": div, "base": base_pv + div, "taux_pfu": pfu(annee),
            "impot_pfu": pfu(annee) * (base_pv + div),
            "report_disponible": sum(s[1] for s in stock),
        }
        if tmi is not None:
            # Bareme : dividendes abattus de 40 % pour l'impot, prelevements sociaux sur le brut.
            ligne["impot_bareme"] = tmi * (base_pv + div * (1 - ABATTEMENT_DIVIDENDES)) + ps * (base_pv + div)
        resultat.append(ligne)
    return sorted(resultat, key=lambda l: -l["annee"])


def pea(versements: float, valeur: float, anciennete: float, type_: str, annee: int) -> dict:
    """Ce que couterait un retrait total aujourd'hui, et ou en est le plafond."""
    gain = max(valeur - versements, 0.0)
    apres = anciennete >= ANCIENNETE_PEA
    taux = prelevements_sociaux(annee) if apres else pfu(annee)
    return {
        "versements": versements, "plafond": PLAFONDS[type_], "reste": PLAFONDS[type_] - versements,
        "anciennete": anciennete, "cinq_ans": apres, "gain_latent": gain,
        "taux_retrait": taux, "impot_retrait": taux * gain,
    }
