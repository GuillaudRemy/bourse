"""Reglages de l'application, stockes en base (table `reglage`) et modifiables dans l'interface.

Chaque reglage connu est declare ici avec sa valeur par defaut, son explication, sa rubrique et
ses choix ; l'interface affiche cette liste telle quelle, en menus deroulants des qu'il y a des choix.
"""
from dataclasses import asdict, dataclass

from sqlmodel import Session, select

from backend.db.db import engine
from backend.db.schema import Reglage


@dataclass(frozen=True)
class Definition:
    cle: str
    libelle: str
    aide: str
    defaut: str = ""
    secret: bool = False
    groupe: str = "Données"
    choix: tuple[tuple[str, str], ...] = ()    # (valeur, libelle) ; rien : saisie libre
    autre: bool = False                        # le menu propose aussi « Autre… »
    source: str = ""                           # choix fournis par l'interface : « valeurs », « modeles »


OUI_NON = (("oui", "Oui"), ("non", "Non"))


def _montants(*valeurs: str, unite: str = "€") -> tuple[tuple[str, str], ...]:
    return tuple((v, f"{v} {unite}") for v in valeurs)


DEFINITIONS = [
    Definition(
        "valeurs_par_page", "Valeurs affichées par page",
        "Nombre de lignes du tableau des valeurs : 20, 50 ou 100 (les autres pages se parcourent en bas du tableau).",
        defaut="50", groupe="Affichage", choix=(("20", "20"), ("50", "50"), ("100", "100")),
    ),
    Definition(
        "actualisation_auto", "Actualisation automatique",
        "« oui » : toutes les valeurs sont actualisées au premier lancement de la journée, puis leurs cours "
        "toutes les heures tant que le logiciel est ouvert. « non » : uniquement à la demande.",
        defaut="oui", groupe="Mises à jour", choix=OUI_NON,
    ),
    Definition(
        "indice_reference", "Indice de référence du portefeuille",
        "Symbole d'une valeur suivie, de préférence dividendes réinvestis (ETF Amundi CAC 40 « CAC.PA », "
        "« ^SP500TR »…). Le portefeuille est comparé au même argent placé dans cet indice aux mêmes dates.",
        defaut="CAC.PA", groupe="Analyse", source="valeurs",
    ),
    Definition(
        "frais_fixe", "Part fixe par ordre",
        "Utilisé pour les nouveaux comptes et le backtest. Exemple : 1 pour « 1 € + 0,1 % ».",
        defaut="0", groupe="Courtage", autre=True, choix=_montants("0", "0,5", "1", "1,5", "1,99", "2", "2,5", "3,8", "5", "9,9"),
    ),
    Definition(
        "frais_pct", "Part proportionnelle",
        "En pourcentage du montant de l'ordre. Exemple : 0,1 pour « 1 € + 0,1 % ».",
        defaut="0,1", groupe="Courtage",
        autre=True, choix=_montants("0", "0,05", "0,1", "0,15", "0,2", "0,25", "0,3", "0,5", "1", unite="%"),
    ),
    Definition("frais_min", "Minimum par ordre", "0 si votre courtier n'en a pas.",
    defaut="0", groupe="Courtage", autre=True, choix=_montants("0", "0,5", "1", "1,5", "1,99", "2", "2,5", "5", "10")),
    Definition(
        "montant_ordre", "Montant habituel d'un ordre",
        "Sert au backtest pour traduire une part fixe de courtage en pourcentage.",
        defaut="2000", groupe="Courtage", autre=True, choix=_montants("500", "1000", "2000", "3000", "5000", "10000"),
    ),
    Definition(
        "prime_risque", "Prime de risque des actions",
        "Rendement exigé d'une action au-delà du taux sans risque (emprunts d'État à 10 ans). Le DCF de l'onglet "
        "Valorisation part de la somme des deux, arrondie au demi-point. 5 % est l'ordre de grandeur historique.",
        defaut="5", groupe="Analyse", autre=True, choix=_montants("3", "3,5", "4", "4,5", "5", "5,5", "6", "6,5", "7", unite="%"),
    ),
    Definition(
        "tranche_marginale", "Tranche marginale d'imposition",
        "Facultatif : sert à comparer la flat tax à l'option pour le barème progressif "
        "dans la fiscalité du compte-titres.",
        groupe="Analyse", choix=(("", "Non renseignée"), *_montants("0", "11", "30", "41", "45", unite="%")),
    ),
    Definition(
        "notifications_bureau", "Notifications sur le bureau",
        "« oui » : une alerte déclenchée s'affiche aussi en notification Windows ou Ubuntu.",
        defaut="oui", groupe="Alertes", choix=OUI_NON,
    ),
    Definition(
        "email_alertes", "Adresse qui reçoit les alertes",
        "Adresse qui reçoit les alertes. Nécessite un serveur d'envoi (SMTP) ci-dessous ; vide : pas d'e-mail.",
        groupe="E-mail des alertes",
    ),
    Definition("smtp_serveur", "Serveur d'envoi (SMTP)",
               "Le service de votre boîte e-mail, ou « Autre… » pour saisir son adresse SMTP.",
    groupe="E-mail des alertes", autre=True, choix=(
        ("", "Aucun"), ("smtp.gmail.com", "Gmail"), ("smtp.office365.com", "Outlook / Hotmail"),
        ("smtp.mail.yahoo.com", "Yahoo"), ("smtp.free.fr", "Free"), ("smtp.orange.fr", "Orange"),
        ("smtp.sfr.fr", "SFR"), ("mail.gmx.com", "GMX"))),
    Definition("smtp_port", "Port SMTP", "587 en général (STARTTLS).",
    defaut="587", groupe="E-mail des alertes", autre=True, choix=(("587", "587 (STARTTLS)"), ("465", "465 (SSL)"), ("25", "25"))),
    Definition("smtp_utilisateur", "Identifiant SMTP", "Souvent l'adresse e-mail elle-même.", groupe="E-mail des alertes"),
    Definition("smtp_mot_de_passe", "Mot de passe SMTP",
               "Pour Gmail : un « mot de passe d'application », pas le mot de passe du compte.",
               secret=True, groupe="E-mail des alertes"),
    Definition(
        "contact_sec", "E-mail de contact pour la SEC",
        "L'administration américaine (SEC) exige une adresse e-mail dans chaque requête. "
        "Sans elle, les comptes des sociétés américaines ne sont pas téléchargés.",
    ),
    Definition(
        "dossier_sauvegarde_externe", "Dossier de sauvegarde externe",
        "Facultatif. Un dossier synchronisé (Google Drive, OneDrive, Nextcloud…) ou une clé USB : la copie "
        "quotidienne de la base y est aussi déposée, dans un sous-dossier Bourse (10 dernières gardées). "
        "Exemple : /home/papa/GoogleDrive ou C:\\Users\\Papa\\OneDrive.",
    ),
    Definition(
        "assistant_modele", "Assistant : modèle Ollama",
        "Nom d'un modèle installé dans Ollama (liste : commande « ollama list »). Vide : choix automatique "
        "(qwen3.5 de préférence). L'assistant fonctionne entièrement sur cet ordinateur, sous Ubuntu pour l'instant.",
        source="modeles",
    ),
    Definition(
        "canal_beta", "Recevoir les versions bêta",
        "« oui » : les versions de test (0.6.0-beta.1…) sont installées dès leur publication, pour les essayer "
        "avant tout le monde. « non » (conseillé) : uniquement les versions stables.",
        defaut="non", groupe="Mises à jour", choix=OUI_NON,
    ),
]
PAR_CLE = {d.cle: d for d in DEFINITIONS}


# Valeurs internes, memorisees mais non affichees dans les reglages.
INTERNES = {"derniere_actualisation", "derniere_tentative", "alertes_initialisees"}


def lire(cle: str) -> str:
    with Session(engine) as db:
        ligne = db.get(Reglage, cle)
    if ligne and ligne.valeur is not None:
        return ligne.valeur
    return PAR_CLE[cle].defaut if cle in PAR_CLE else ""


def ecrire(cle: str, valeur: str | None) -> None:
    with Session(engine) as db:
        ligne = db.get(Reglage, cle) or Reglage(cle=cle)
        ligne.valeur = (valeur or "").strip() or None
        db.add(ligne)
        db.commit()


def tous() -> list[dict]:
    with Session(engine) as db:
        valeurs = {r.cle: r.valeur for r in db.exec(select(Reglage))}
    return [
        {**asdict(d), "valeur": ("••••••" if d.secret and valeurs.get(d.cle) else valeurs.get(d.cle) or "")}
        for d in DEFINITIONS
    ]


def nombre(cle: str, defaut: float = 0.0) -> float:
    """Reglage numerique (« 0,1 » ou « 0.1 ») ; `defaut` si vide ou illisible."""
    try:
        return float(lire(cle).replace(",", ".").replace("%", "").replace("€", "").strip())
    except ValueError:
        return defaut


def grille_frais() -> dict:
    """Grille de courtage par defaut, pourcentage en fraction."""
    return {"fixe": nombre("frais_fixe"), "pct": nombre("frais_pct") / 100, "min": nombre("frais_min")}
