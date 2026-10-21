"""Reglages de l'application, stockes en base (table `reglage`) et modifiables dans l'interface.

Chaque reglage connu est declare ici avec sa valeur par defaut et son explication ;
l'interface affiche cette liste telle quelle.
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


DEFINITIONS = [
    Definition(
        "actualisation_auto", "Actualisation automatique quotidienne",
        "« oui » : au premier lancement de la journée, toutes les valeurs sont actualisées en tâche de fond. "
        "« non » : uniquement à la demande.",
        defaut="oui",
    ),
    Definition(
        "indice_reference", "Indice de référence du portefeuille",
        "Symbole d'une valeur suivie, de préférence dividendes réinvestis (ETF Amundi CAC 40 « CAC.PA », "
        "« ^SP500TR »…). Le portefeuille est comparé au même argent placé dans cet indice aux mêmes dates.",
        defaut="CAC.PA",
    ),
    Definition(
        "frais_fixe", "Courtage par défaut : part fixe (€ par ordre)",
        "Utilisé pour les nouveaux comptes et le backtest. Exemple : 1 pour « 1 € + 0,1 % ».", defaut="0",
    ),
    Definition(
        "frais_pct", "Courtage par défaut : part proportionnelle (%)",
        "En pourcentage du montant de l'ordre. Exemple : 0,1 pour « 1 € + 0,1 % ».", defaut="0,1",
    ),
    Definition("frais_min", "Courtage par défaut : minimum par ordre (€)", "0 si votre courtier n'en a pas.", defaut="0"),
    Definition(
        "montant_ordre", "Montant habituel d'un ordre (€)",
        "Sert au backtest pour traduire une part fixe de courtage en pourcentage.", defaut="2000",
    ),
    Definition(
        "tranche_marginale", "Tranche marginale d'imposition (TMI)",
        "En % : 0, 11, 30, 41 ou 45. Facultatif : sert à comparer la flat tax à l'option pour le barème progressif "
        "dans la fiscalité du compte-titres.",
    ),
    Definition(
        "notifications_bureau", "Notifications sur le bureau",
        "« oui » : une alerte déclenchée s'affiche aussi en notification Windows ou Ubuntu.", defaut="oui",
    ),
    Definition(
        "email_alertes", "E-mail pour recevoir les alertes",
        "Adresse qui reçoit les alertes. Nécessite un serveur d'envoi (SMTP) ci-dessous ; vide : pas d'e-mail.",
    ),
    Definition("smtp_serveur", "Serveur d'envoi (SMTP)", "Exemple : smtp.gmail.com (port 587)."),
    Definition("smtp_port", "Port SMTP", "587 en général (STARTTLS).", defaut="587"),
    Definition("smtp_utilisateur", "Identifiant SMTP", "Souvent l'adresse e-mail elle-même."),
    Definition("smtp_mot_de_passe", "Mot de passe SMTP",
               "Pour Gmail : un « mot de passe d'application », pas le mot de passe du compte.", secret=True),
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
    ),
    Definition(
        "canal_beta", "Recevoir les versions bêta",
        "« oui » : les versions de test (0.6.0-beta.1…) sont installées dès leur publication, pour les essayer "
        "avant tout le monde. « non » (conseillé) : uniquement les versions stables.",
        defaut="non",
    ),
]
PAR_CLE = {d.cle: d for d in DEFINITIONS}


# Valeurs internes, memorisees mais non affichees dans les reglages.
INTERNES = {"derniere_actualisation", "alertes_initialisees"}


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
