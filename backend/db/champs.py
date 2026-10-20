"""Les postes des etats financiers annuels, en un seul endroit.

Chaque poste a une cle (colonne de la table `fondamental`), un libelle, l'etat auquel il
appartient et son unite. Le backend (sources, ratios) et l'interface (tableaux) lisent
tous cette liste : ajouter un poste ici, plus une migration, suffit a le faire apparaitre.

Les montants sont dans la devise de publication de l'entreprise. Les depenses (capex,
dividendes verses, rachats) sont stockees en valeur POSITIVE.
"""
from dataclasses import asdict, dataclass

RESULTAT, BILAN, FLUX, ACTION = "resultat", "bilan", "flux", "action"
MONNAIE, PAR_ACTION, NOMBRE = "monnaie", "par_action", "nombre"


@dataclass(frozen=True)
class Champ:
    cle: str
    libelle: str
    etat: str
    unite: str = MONNAIE
    aide: str = ""


CHAMPS: list[Champ] = [
    # ── Compte de resultat ──
    Champ("chiffre_affaires", "Chiffre d'affaires", RESULTAT),
    Champ("marge_brute", "Marge brute", RESULTAT, aide="Chiffre d'affaires moins le coût des ventes."),
    Champ("frais_generaux", "Frais commerciaux et généraux", RESULTAT),
    Champ("ebitda", "EBITDA", RESULTAT, aide="Résultat opérationnel avant amortissements."),
    Champ("amortissements", "Amortissements", RESULTAT),
    Champ("ebit", "Résultat opérationnel (EBIT)", RESULTAT),
    Champ("charges_interets", "Charges d'intérêts", RESULTAT),
    Champ("benefice_net", "Bénéfice net (part du groupe)", RESULTAT),
    # ── Par action ──
    Champ("bpa", "BPA dilué", ACTION, PAR_ACTION, "Bénéfice net par action, dilué."),
    Champ("dividende", "Dividende par action", ACTION, PAR_ACTION, "Dividende versé au titre de l'année."),
    Champ("nombre_actions", "Nombre d'actions (moyen dilué)", ACTION, NOMBRE),
    # ── Bilan (fin d'exercice) ──
    Champ("total_actif", "Total de l'actif", BILAN),
    Champ("actifs_courants", "Actifs courants", BILAN),
    Champ("tresorerie", "Trésorerie", BILAN),
    Champ("creances_clients", "Créances clients", BILAN),
    Champ("immobilisations_corporelles", "Immobilisations corporelles", BILAN),
    Champ("goodwill", "Écarts d'acquisition (goodwill)", BILAN),
    Champ("passifs_courants", "Passifs courants", BILAN),
    Champ("total_passif", "Total des dettes (hors capitaux propres)", BILAN),
    Champ("dette_financiere", "Dette financière brute", BILAN, aide="Emprunts courts et longs terme."),
    Champ("dette_long_terme", "Dette financière à long terme", BILAN),
    Champ("capitaux_propres", "Capitaux propres (part du groupe)", BILAN),
    Champ("resultats_non_distribues", "Réserves (résultats non distribués)", BILAN),
    # ── Flux de tresorerie ──
    Champ("flux_operationnel", "Flux de trésorerie opérationnel", FLUX),
    Champ("capex", "Investissements (capex)", FLUX, aide="Achats d'immobilisations, en valeur positive."),
    Champ("dividendes_verses", "Dividendes versés", FLUX),
    Champ("rachats_actions", "Rachats d'actions", FLUX),
]

PAR_CLE = {c.cle: c for c in CHAMPS}
CLES = [c.cle for c in CHAMPS]
# Postes exprimes par action : a ajuster des divisions d'actions posterieures.
PAR_ACTION_CLES = [c.cle for c in CHAMPS if c.unite == PAR_ACTION]

# Priorite des sources : une donnee n'est remplacee que par une source au moins aussi fiable.
PRIORITE = {"manuel": 4, "import": 4, "pdf": 4, "sec": 3, "esef": 3, "yahoo": 2}


def catalogue() -> list[dict]:
    return [asdict(c) for c in CHAMPS]
