"""Partage entre plusieurs PC par fichier (.bourse.json) : export, apercu, import.

Le fichier contient ce que l'utilisateur a construit lui-meme : valeurs suivies, these,
decisions, traces, alertes, listes, filtres du screener, comptes saisis a la main, cours des
valeurs importees, et le portefeuille si on le demande. Ce qui se telecharge (cours Yahoo,
comptes SEC/ESEF) n'y est pas : l'autre PC le retelecharge.

Import : on AJOUTE, on n'ecrase jamais. Une valeur deja suivie garde ses reglages ; une
decision, un trace ou une alerte identique n'est pas doublee ; une case de comptes deja
remplie localement par une source au moins aussi fiable est conservee.
"""
import json
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlmodel import Session, col, select

from backend.core.config import config
from backend.db.champs import CLES, PRIORITE
from backend.db.schema import (
    Alerte,
    Annotation,
    Compte,
    Cours,
    Decision,
    Filtre,
    Fondamental,
    Liste,
    ListeValeur,
    These,
    Transaction,
    Valeur,
)
from backend.services import cache
from backend.services.stockage import enregistrer_fondamentaux, provenance

FORMAT, VERSION = "bourse-partage", 1
SOURCES_SAISIES = {"manuel", "import", "pdf"}
CHAMPS_VALEUR = ["symbole", "nom", "type", "source", "devise", "place", "secteur", "pays", "isin", "lei", "cik",
                 "devise_comptes", "debut_regression", "rupture", "notes"]


def _json(objet) -> dict:
    """Champs d'une ligne sans identifiants internes, dates en texte."""
    donnees = objet.model_dump(exclude={"id", "valeur_id", "compte_id", "alerte_id", "liste_id", "created_at"})
    return {k: v.isoformat() if isinstance(v, date | datetime) else v for k, v in donnees.items()}


def exporter(db: Session, portefeuille: bool) -> dict:
    valeurs = list(db.exec(select(Valeur).order_by(col(Valeur.symbole))))
    symboles = {v.id: v.symbole for v in valeurs}
    contenu = []
    for v in valeurs:
        fiche = {k: getattr(v, k) for k in CHAMPS_VALEUR}
        fiche["debut_regression"] = v.debut_regression.isoformat() if v.debut_regression else None
        these = db.exec(select(These).where(These.valeur_id == v.id)).first()
        fiche["these"] = _json(these) if these else None
        fiche["decisions"] = [_json(d) for d in db.exec(select(Decision).where(Decision.valeur_id == v.id))]
        fiche["annotations"] = [_json(a) for a in db.exec(select(Annotation).where(Annotation.valeur_id == v.id))]
        fiche["alertes"] = [{"type": a.type, "seuil": a.seuil, "active": a.active}
                            for a in db.exec(select(Alerte).where(Alerte.valeur_id == v.id))]
        saisis = []
        for f in db.exec(select(Fondamental).where(Fondamental.valeur_id == v.id).order_by(col(Fondamental.annee))):
            origine = provenance(f)
            champs = {c: getattr(f, c) for c in CLES if origine.get(c) in SOURCES_SAISIES and getattr(f, c) is not None}
            if champs:
                saisis.append({"annee": f.annee, "champs": champs, "sources": {c: origine[c] for c in champs}})
        fiche["comptes_saisis"] = saisis
        if v.source not in ("yahoo", "bce"):   # cours importes : introuvables ailleurs
            fiche["cours"] = [[c.jour.isoformat(), c.cloture, c.ajuste, c.ouverture, c.haut, c.bas, c.volume]
                              for c in db.exec(select(Cours).where(Cours.valeur_id == v.id).order_by(col(Cours.jour)))]
        contenu.append(fiche)

    listes = []
    for liste in db.exec(select(Liste).order_by(col(Liste.nom))):
        membres = db.exec(select(ListeValeur).where(ListeValeur.liste_id == liste.id))
        listes.append({"nom": liste.nom, "symboles": sorted(symboles[m.valeur_id] for m in membres)})
    resultat = {
        "format": FORMAT, "version": VERSION, "application": config.APP_VERSION,
        "exporte_le": datetime.now(UTC).isoformat(timespec="seconds"),
        "valeurs": contenu, "listes": listes,
        "filtres": [{"nom": f.nom, "criteres": f.criteres} for f in db.exec(select(Filtre).order_by(col(Filtre.nom)))],
    }
    if portefeuille:
        resultat["comptes"] = [
            {**_json(c), "transactions": [{**_json(t), "symbole": symboles.get(t.valeur_id)}
                                          for t in db.exec(select(Transaction).where(Transaction.compte_id == c.id)
                                                           .order_by(col(Transaction.jour)))]}
            for c in db.exec(select(Compte).order_by(col(Compte.nom)))]
    return resultat


def _lire(contenu: bytes) -> dict:
    try:
        donnees = json.loads(contenu)
    except ValueError as e:
        raise HTTPException(400, "Ce fichier n'est pas un export de Bourse (JSON illisible).") from e
    if not isinstance(donnees, dict) or donnees.get("format") != FORMAT:
        raise HTTPException(400, "Ce fichier n'est pas un export de Bourse.")
    if donnees.get("version", 0) > VERSION:
        raise HTTPException(400, "Export fait par une version plus récente de Bourse : mettez d'abord celle-ci à jour.")
    return donnees


def apercu(db: Session, contenu: bytes) -> dict:
    donnees = _lire(contenu)
    connues = {v.symbole for v in db.exec(select(Valeur))}
    nouvelles = [v["symbole"] for v in donnees["valeurs"] if v["symbole"] not in connues]
    return {
        "application": donnees.get("application"), "exporte_le": donnees.get("exporte_le"),
        "valeurs": len(donnees["valeurs"]), "nouvelles_valeurs": nouvelles,
        "theses": sum(1 for v in donnees["valeurs"] if v.get("these")),
        "decisions": sum(len(v.get("decisions", [])) for v in donnees["valeurs"]),
        "annotations": sum(len(v.get("annotations", [])) for v in donnees["valeurs"]),
        "alertes": sum(len(v.get("alertes", [])) for v in donnees["valeurs"]),
        "annees_comptes_saisis": sum(len(v.get("comptes_saisis", [])) for v in donnees["valeurs"]),
        "listes": len(donnees.get("listes", [])), "filtres": len(donnees.get("filtres", [])),
        "comptes": len(donnees.get("comptes", [])),
        "transactions": sum(len(c.get("transactions", [])) for c in donnees.get("comptes", [])),
    }


def _id(ligne) -> int:
    """Identifiant d'une ligne enregistree (connu apres flush)."""
    assert ligne.id is not None
    return ligne.id


def _date(texte):
    return date.fromisoformat(texte[:10]) if texte else None


def importer(db: Session, contenu: bytes, portefeuille: bool) -> dict:
    donnees = _lire(contenu)
    compte = dict.fromkeys(["valeurs", "theses", "decisions", "annotations", "alertes", "comptes_saisis",
                            "listes", "filtres", "comptes", "transactions"], 0)
    a_telecharger: list[int] = []
    par_symbole = {v.symbole: v for v in db.exec(select(Valeur))}

    for fiche in donnees["valeurs"]:
        v = par_symbole.get(fiche["symbole"])
        if v is None:
            champs = {k: fiche.get(k) for k in CHAMPS_VALEUR if fiche.get(k) is not None}
            champs["debut_regression"] = _date(champs.get("debut_regression"))
            v = Valeur(**champs)
            db.add(v)
            db.flush()
            par_symbole[v.symbole] = v
            compte["valeurs"] += 1
            if v.source in ("yahoo", "bce"):
                a_telecharger.append(_id(v))
            for ligne in fiche.get("cours", []):
                jour, cloture, ajuste, ouverture, haut, bas, volume = ligne
                db.add(Cours(valeur_id=_id(v), jour=_date(jour), cloture=cloture, ajuste=ajuste, ouverture=ouverture,
                             haut=haut, bas=bas, volume=volume))

        if fiche.get("these") and not db.exec(select(These).where(These.valeur_id == _id(v))).first():
            t = fiche["these"]
            db.add(These(valeur_id=_id(v), **{k: t.get(k) for k in ("pourquoi", "avantage", "risques", "prix_achat",
                                                                   "prix_vente", "conditions", "checklist")}))
            compte["theses"] += 1

        existantes = {(d.jour.isoformat(), d.type, d.prix, d.raison)
                      for d in db.exec(select(Decision).where(Decision.valeur_id == _id(v)))}
        for d in fiche.get("decisions", []):
            if (d["jour"][:10], d["type"], d.get("prix"), d.get("raison")) not in existantes:
                db.add(Decision(valeur_id=_id(v), jour=_date(d["jour"]), type=d["type"], prix=d.get("prix"),
                                raison=d.get("raison"), relecture=d.get("relecture"), verdict=d.get("verdict")))
                compte["decisions"] += 1

        traces = {(a.type, a.donnees) for a in db.exec(select(Annotation).where(Annotation.valeur_id == _id(v)))}
        for a in fiche.get("annotations", []):
            if (a["type"], a["donnees"]) not in traces:
                db.add(Annotation(valeur_id=_id(v), type=a["type"], donnees=a["donnees"]))
                compte["annotations"] += 1

        regles = {(a.type, a.seuil) for a in db.exec(select(Alerte).where(Alerte.valeur_id == _id(v)))}
        for a in fiche.get("alertes", []):
            if (a["type"], a.get("seuil")) not in regles:
                db.add(Alerte(valeur_id=_id(v), type=a["type"], seuil=a.get("seuil"), active=a.get("active", True)))
                compte["alertes"] += 1

        compte["comptes_saisis"] += _fusionner_comptes(db, _id(v), fiche.get("comptes_saisis", []))

    for liste in donnees.get("listes", []):
        locale = db.exec(select(Liste).where(Liste.nom == liste["nom"])).first()
        if locale is None:
            locale = Liste(nom=liste["nom"])
            db.add(locale)
            db.flush()
            compte["listes"] += 1
        membres = {m.valeur_id for m in db.exec(select(ListeValeur).where(ListeValeur.liste_id == _id(locale)))}
        for symbole in liste["symboles"]:
            if (v := par_symbole.get(symbole)) and _id(v) not in membres:
                db.add(ListeValeur(liste_id=_id(locale), valeur_id=_id(v)))

    for f in donnees.get("filtres", []):
        if not db.exec(select(Filtre).where(Filtre.nom == f["nom"])).first():
            db.add(Filtre(nom=f["nom"], criteres=f["criteres"]))
            compte["filtres"] += 1

    if portefeuille:
        for c in donnees.get("comptes", []):
            if db.exec(select(Compte).where(Compte.nom == c["nom"])).first():
                continue                  # compte deja present : on ne melange pas deux historiques
            local = Compte(**{k: c.get(k) for k in ("nom", "type", "courtier", "frais_fixe", "frais_pct", "frais_min")},
                           ouverture=_date(c.get("ouverture")))
            db.add(local)
            db.flush()
            compte["comptes"] += 1
            for t in c.get("transactions", []):
                v = par_symbole.get(t.get("symbole")) if t.get("symbole") else None
                db.add(Transaction(compte_id=_id(local), valeur_id=_id(v) if v else None, jour=_date(t["jour"]), type=t["type"],
                                   **{k: t.get(k) for k in ("quantite", "prix", "montant", "note")},
                                   frais=t.get("frais") or 0.0, ttf=t.get("ttf") or 0.0))
                compte["transactions"] += 1

    db.commit()
    cache.invalider()
    if a_telecharger:
        from backend.services import taches
        taches.lancer()               # telecharge les nouvelles valeurs (et actualise les autres)
    return {**compte, "a_telecharger": len(a_telecharger)}


def _fusionner_comptes(db: Session, valeur_id: int, saisis: list[dict]) -> int:
    """N'ajoute une case que si la case locale est vide ou d'une source moins fiable."""
    locales = {f.annee: provenance(f) for f in db.exec(select(Fondamental).where(Fondamental.valeur_id == valeur_id))}
    ajoutees = 0
    for annee in saisis:
        origine_locale = locales.get(annee["annee"], {})
        par_source: dict[str, dict] = {}
        for cle, valeur in annee["champs"].items():
            source = annee["sources"].get(cle, "manuel")
            locale = origine_locale.get(cle)
            if cle in CLES and (PRIORITE.get(locale, 0) if locale else 0) < PRIORITE.get(source, 0):
                par_source.setdefault(source, {})[cle] = valeur
        for source, champs in par_source.items():
            ajoutees += enregistrer_fondamentaux(db, valeur_id, {annee["annee"]: champs}, source) and len(champs)
    return ajoutees
