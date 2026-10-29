"""Alertes : evaluees apres chaque actualisation d'une valeur.

Une alerte se declenche quand sa condition DEVIENT vraie (pas tous les jours tant qu'elle
le reste) : `derniere` garde la date du declenchement et se remet a zero quand la condition
redevient fausse.

Notification : dans l'application (cloche), sur le bureau (Windows, Ubuntu) et par e-mail
si un serveur d'envoi est configure dans les reglages. Une notification qui echoue ne
bloque jamais l'actualisation.
"""
import shutil
import smtplib
import subprocess
import sys
from datetime import date
from email.message import EmailMessage

import pandas as pd
from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from backend.analyse import indicateurs as ind
from backend.analyse.regression import ajuster
from backend.core import reglages
from backend.core.config import config
from backend.db.schema import Alerte, Declenchement, Valeur
from backend.services.stockage import charger_cours
from backend.sources import catalogue

TYPES = {
    "sigma_sous":      ("Position dans le couloir ≤", "σ"),
    "sigma_dessus":    ("Position dans le couloir ≥", "σ"),
    "rsi_sous":        ("RSI 14 ≤", ""),
    "rsi_dessus":      ("RSI 14 ≥", ""),
    "cours_sous":      ("Cours ≤", ""),
    "cours_dessus":    ("Cours ≥", ""),
    "croisement_dore": ("Croisement doré (MM50 passe au-dessus de la MM200)", None),
    "croisement_mort": ("Croisement de la mort (MM50 passe sous la MM200)", None),
}
# Pour chaque nouvelle action suivie : prevenir quand elle entre dans les zones extremes du couloir.
PAR_DEFAUT = [("sigma_sous", -2.0), ("sigma_dessus", 2.0)]


def libelle(alerte: Alerte) -> str:
    texte, unite = TYPES[alerte.type]
    return texte if unite is None else f"{texte} {alerte.seuil:g} {unite}".strip().replace(".", ",")


def creer_par_defaut(db: Session, valeur: Valeur) -> None:
    if valeur.type != "action":
        return
    for type_, seuil in PAR_DEFAUT:
        db.add(Alerte(valeur_id=_id(valeur), type=type_, seuil=seuil))


def _id(valeur: Valeur) -> int:
    assert valeur.id is not None, "valeur non enregistree"
    return valeur.id


def _mesures(db: Session, valeur: Valeur) -> dict:
    cours = charger_cours(db, _id(valeur))
    if cours.empty:
        return {}
    cloture = cours["cloture"]
    base = (cours["ajuste"] if cours["ajuste"].notna().mean() > 0.9 else cloture).dropna()
    from backend.services.analyse_service import debut_par_defaut  # import tardif : evite un cycle
    debut = valeur.debut_regression or debut_par_defaut(valeur)[0]
    reg = None if valeur.type in catalogue.SANS_DROITE else ajuster(base[base.index >= pd.Timestamp(debut)])
    mm50, mm200 = ind.moyenne_mobile(cloture, 50), ind.moyenne_mobile(cloture, 200)
    ecart = (mm50 - mm200).dropna().tail(6)
    return {
        "position": reg.position if reg else None,
        "rsi": float(ind.rsi(cloture).iloc[-1]) if len(cloture) > 20 else None,
        "cours": float(cloture.iloc[-1]),
        "dore": bool(len(ecart) > 1 and ecart.iloc[-1] > 0 and (ecart.iloc[:-1] <= 0).any()),
        "mort": bool(len(ecart) > 1 and ecart.iloc[-1] < 0 and (ecart.iloc[:-1] >= 0).any()),
    }


def _vraie(alerte: Alerte, m: dict) -> bool:
    valeur = {"sigma": m.get("position"), "rsi": m.get("rsi"), "cours": m.get("cours")}
    if alerte.type == "croisement_dore":
        return m.get("dore", False)
    if alerte.type == "croisement_mort":
        return m.get("mort", False)
    mesure = valeur[alerte.type.split("_")[0]]
    if mesure is None or alerte.seuil is None:
        return False
    return mesure <= alerte.seuil if alerte.type.endswith("_sous") else mesure >= alerte.seuil


def evaluer(db: Session, valeur_id: int) -> list[Declenchement]:
    valeur = db.get(Valeur, valeur_id)
    alertes = list(db.exec(select(Alerte).where(Alerte.valeur_id == valeur_id, Alerte.active == True)))
    if not valeur or not alertes:
        return []
    mesures = _mesures(db, valeur)
    if not mesures:
        return []
    nouveaux = []
    for alerte in alertes:
        if _vraie(alerte, mesures):
            if alerte.derniere is None:
                alerte.derniere = date.today()
                details = f" (position {mesures['position']:+.2f} σ, cours {mesures['cours']:.2f})".replace(".", ",") \
                    if mesures.get("position") is not None else ""
                d = Declenchement(alerte_id=alerte.id, valeur_id=valeur_id,
                                  message=f"{valeur.nom} : {libelle(alerte)}{details}")
                db.add(d)
                nouveaux.append(d)
        else:
            alerte.derniere = None
    db.commit()
    if nouveaux:
        notifier([d.message for d in nouveaux])
    return nouveaux


# ── Notifications ────────────────────────────────────────────────────
def notifier(messages: list[str]) -> list[str]:
    """Renvoie les canaux utilises ; n'echoue jamais."""
    canaux: list[str] = []
    if not config.NOTIFICATIONS:
        return canaux
    if reglages.lire("notifications_bureau") == "oui" and _bureau(messages):
        canaux.append("bureau")
    if reglages.lire("email_alertes") and _email(messages):
        canaux.append("email")
    return canaux


def _bureau(messages: list[str]) -> bool:
    titre = "Bourse — alerte" if len(messages) == 1 else f"Bourse — {len(messages)} alertes"
    corps = "\n".join(messages[:5])
    try:
        if sys.platform.startswith("linux") and shutil.which("notify-send"):
            subprocess.run(["notify-send", "-a", "Bourse", titre, corps], timeout=10, check=False)
            return True
        if sys.platform == "win32":
            # Notification Windows 10/11 via PowerShell, sans module supplementaire.
            script = (
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                "ContentType = WindowsRuntime] > $null;"
                "$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
                "[Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
                "$t = $x.GetElementsByTagName('text');"
                f"$t.Item(0).AppendChild($x.CreateTextNode({_ps(titre)})) > $null;"
                f"$t.Item(1).AppendChild($x.CreateTextNode({_ps(corps)})) > $null;"
                "$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe';"
                "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show("
                "[Windows.UI.Notifications.ToastNotification]::new($x))"
            )
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                           timeout=20, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return True
    except (OSError, subprocess.SubprocessError):
        return False
    return False


def _ps(texte: str) -> str:
    return "'" + texte.replace("'", "''") + "'"


def _email(messages: list[str]) -> bool:
    serveur = reglages.lire("smtp_serveur")
    if not serveur:
        return False
    message = EmailMessage()
    message["Subject"] = "Bourse : " + (messages[0] if len(messages) == 1 else f"{len(messages)} alertes")
    message["From"] = reglages.lire("smtp_utilisateur") or reglages.lire("email_alertes")
    message["To"] = reglages.lire("email_alertes")
    message.set_content("\n".join(messages) + "\n\n— Bourse, analyse des cours et des fondamentaux")
    try:
        port = int(reglages.lire("smtp_port") or 587)
        with smtplib.SMTP(serveur, port, timeout=20) as smtp:
            smtp.starttls()
            if reglages.lire("smtp_utilisateur"):
                smtp.login(reglages.lire("smtp_utilisateur"), reglages.lire("smtp_mot_de_passe"))
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException, ValueError):
        return False


# ── Lecture ──────────────────────────────────────────────────────────
class AlerteService:
    def __init__(self, session: Session):
        self._db = session

    def alertes(self, valeur_id: int | None = None) -> list[dict]:
        requete = select(Alerte, Valeur).join(Valeur, col(Valeur.id) == col(Alerte.valeur_id))
        if valeur_id:
            requete = requete.where(Alerte.valeur_id == valeur_id)
        return [{"id": a.id, "valeur_id": a.valeur_id, "valeur": v.nom, "type": a.type, "seuil": a.seuil,
                 "active": a.active, "derniere": a.derniere, "libelle": libelle(a)}
                for a, v in self._db.exec(requete.order_by(Valeur.nom))]

    def ecrire(self, valeur_id: int, type_: str, seuil: float | None, active: bool = True,
               alerte_id: int | None = None) -> dict:
        if type_ not in TYPES:
            raise HTTPException(422, "Type d'alerte inconnu.")
        if TYPES[type_][1] is not None and seuil is None:
            raise HTTPException(422, "Cette alerte demande un seuil.")
        if not self._db.get(Valeur, valeur_id):
            raise HTTPException(404, "Valeur introuvable.")
        alerte = self._db.get(Alerte, alerte_id) if alerte_id else Alerte(valeur_id=valeur_id, type=type_)
        if alerte is None:
            raise HTTPException(404, "Alerte introuvable.")
        alerte.type, alerte.seuil, alerte.active, alerte.derniere = type_, seuil, active, None
        self._db.add(alerte)
        self._db.commit()
        evaluer(self._db, valeur_id)
        return next(a for a in self.alertes(valeur_id) if a["id"] == alerte.id)

    def supprimer(self, alerte_id: int) -> None:
        alerte = self._db.get(Alerte, alerte_id)
        if not alerte:
            raise HTTPException(404, "Alerte introuvable.")
        self._db.delete(alerte)
        self._db.commit()

    def declenchements(self, limite: int = 100) -> dict:
        lignes = self._db.exec(select(Declenchement).order_by(col(Declenchement.moment).desc()).limit(limite))
        non_lus = self._db.exec(select(func.count()).select_from(Declenchement).where(Declenchement.lu == False)).one()
        return {"non_lus": non_lus, "liste": [d.model_dump(mode="json") for d in lignes]}

    def marquer_lus(self) -> None:
        for d in self._db.exec(select(Declenchement).where(Declenchement.lu == False)):
            d.lu = True
        self._db.commit()
