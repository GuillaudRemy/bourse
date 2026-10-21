"""Assistant local (Ollama) : lecture de rapport annuel, questions sur la fiche, resume des actualites.

Toujours une aide, jamais une decision : chaque point cite ses pages, et l'interface rappelle
que le modele peut se tromper. Rien ne quitte l'ordinateur (voir sources/ollama.py).

Lecture d'un rapport annuel (200 a 400 pages, bien trop pour un petit modele en une fois) :
  1. texte page par page (pdfplumber) ;
  2. selection des pages utiles par mots-cles (risques, strategie, perspectives, signaux de
     rupture, lettre aux actionnaires) ;
  3. extraction par lots de 3 pages : des points courts, chacun avec sa page ;
  4. synthese : risques, strategie, perspectives, signaux de rupture, questions a verifier.
"""
import contextlib
import io
import json
import re
import threading
import time
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlmodel import Session, col, select

from backend.core import reglages
from backend.db.db import engine
from backend.db.schema import AnalyseIA, Valeur
from backend.sources import ollama

PAGES_MAX = 30                 # pages retenues dans un rapport
PAGES_PAR_LOT = 3
CARACTERES_PAR_LOT = 9000      # environ 2 500 jetons : tient avec la consigne dans 8 192
POINTS_MAX = 60                # points transmis au resume
PRUDENCE = ("Tu aides un investisseur particulier a lire des documents. Reponds en francais. "
            "Appuie-toi uniquement sur le texte fourni ; n'invente rien ; si l'information manque, dis-le. "
            "Ne donne jamais de conseil d'achat ou de vente.")

# Mots-cles (francais et anglais) et leur poids pour reperer les pages utiles.
MOTS_CLES = {
    "risque": (3, ["facteurs de risque", "principaux risques", "risk factors", "gestion des risques", "risques"]),
    "strategie": (2, ["stratégie", "strategy", "plan stratégique", "ambition", "objectifs", "priorités"]),
    "perspective": (2, ["perspectives", "outlook", "guidance", "prévisions", "tendances"]),
    "rupture": (3, ["acquisition", "cession", "restructuration", "dépréciation", "impairment", "litige", "enquête",
                    "fusion", "scission", "spin-off", "plan de transformation", "réorganisation", "abandon",
                    "nouveau directeur général", "changement de gouvernance", "covenant", "going concern"]),
    "lettre": (4, ["chers actionnaires", "message du président", "message du directeur général",
                   "letter to shareholders", "dear shareholders", "entretien avec"]),
}
CATEGORIES = ["risque", "strategie", "perspective", "rupture"]

# Pas de format JSON impose : essaye sur de vrais rapports, qwen3.5 (Ollama 0.20) ignore la contrainte
# des que l'extrait est long et repond en liste a puces. On demande donc des lignes balisees, relues
# de facon tolerante. Pas non plus de « niveau de rupture » : un modele de cette taille ne sait pas juger
# la portee d'un fait (une cession ancienne et marginale devenait un « signal fort ») ; il releve les
# faits avec leurs pages, le jugement reste a l'utilisateur.
TONS = ["plutôt positif", "plutôt négatif", "neutre", "partagé"]

_travaux: dict[str, dict] = {}
_verrou = threading.Lock()


# ── Etat ───────────────────────────────────────────────────────────────
def etat() -> dict:
    return ollama.etat(reglages.lire("assistant_modele") or None)


def _modele() -> str:
    e = etat()
    if not e["disponible"]:
        raise HTTPException(409, e["raison"])
    return e["modele"]


def _valeur(db: Session, valeur_id: int) -> Valeur:
    v = db.get(Valeur, valeur_id)
    if v is None:
        raise HTTPException(404, "Valeur introuvable.")
    return v


def _enregistrer(valeur_id: int, type_: str, titre: str, modele: str, debut: float, resultat: dict) -> int:
    with Session(engine) as db:
        ligne = AnalyseIA(valeur_id=valeur_id, type=type_, titre=titre, modele=modele,
                          duree=round(time.monotonic() - debut, 1), resultat=json.dumps(resultat, ensure_ascii=False))
        db.add(ligne)
        db.commit()
        assert ligne.id is not None
        return ligne.id


def analyses(db: Session, valeur_id: int) -> list[dict]:
    lignes = db.exec(select(AnalyseIA).where(AnalyseIA.valeur_id == valeur_id).order_by(col(AnalyseIA.created_at).desc()))
    return [{"id": a.id, "type": a.type, "titre": a.titre, "modele": a.modele, "duree": a.duree,
             "date": a.created_at.isoformat(), "resultat": json.loads(a.resultat)} for a in lignes]


def supprimer(db: Session, valeur_id: int, analyse_id: int) -> None:
    a = db.get(AnalyseIA, analyse_id)
    if a is None or a.valeur_id != valeur_id:
        raise HTTPException(404, "Analyse introuvable.")
    db.delete(a)
    db.commit()


def travail(travail_id: str) -> dict:
    with _verrou:
        if travail_id not in _travaux:
            raise HTTPException(404, "Travail inconnu.")
        return dict(_travaux[travail_id])


# ── Rapport annuel ─────────────────────────────────────────────────────
def pages_pdf(contenu: bytes) -> list[str]:
    import pdfplumber
    with pdfplumber.open(io.BytesIO(contenu)) as document:
        return [(p.extract_text() or "") for p in document.pages]


def selectionner(pages: list[str], maximum: int = PAGES_MAX) -> list[int]:
    """Numeros (1 = premiere page) des pages les plus utiles, dans l'ordre du document."""
    scores = []
    for numero, texte in enumerate(pages, start=1):
        bas = texte.lower()
        if len(bas) < 300:                       # page de garde, intercalaire, image
            continue
        score = sum(poids * bas.count(mot) for poids, mots in MOTS_CLES.values() for mot in mots)
        # Les sommaires citent tous les mots-cles sans rien dire : on les ecarte.
        if bas.count("....") > 5 or len(re.findall(r"\n\s*\d{1,3}\s*$", bas, re.M)) > 15:
            score = 0
        if score:
            scores.append((score, numero))
    retenues = sorted(n for _, n in sorted(scores, reverse=True)[:maximum])
    return retenues


def _lots(pages: list[str], numeros: list[int]) -> list[str]:
    lots, courant = [], []
    for n in numeros:
        courant.append(f"[page {n}]\n{pages[n - 1][:CARACTERES_PAR_LOT // PAGES_PAR_LOT]}")
        if len(courant) == PAGES_PAR_LOT:
            lots.append("\n\n".join(courant))
            courant = []
    if courant:
        lots.append("\n\n".join(courant))
    return lots


def lancer_rapport(db: Session, valeur_id: int, nom: str, contenu: bytes) -> str:
    valeur = _valeur(db, valeur_id)
    modele = _modele()
    travail_id = uuid.uuid4().hex[:12]
    with _verrou:
        _travaux[travail_id] = {"etape": "Lecture du PDF", "fait": 0, "total": 0, "termine": False,
                                "erreur": None, "analyse_id": None}
    threading.Thread(target=_lire_rapport, args=(travail_id, valeur_id, valeur.nom, nom, contenu, modele),
                     daemon=True, name="assistant-rapport").start()
    return travail_id


def _maj(travail_id: str, **champs) -> None:
    with _verrou:
        _travaux[travail_id].update(champs)


def _lire_rapport(travail_id: str, valeur_id: int, societe: str, nom: str, contenu: bytes, modele: str) -> None:
    debut = time.monotonic()
    try:
        pages = pages_pdf(contenu)
        numeros = selectionner(pages)
        if not numeros:
            raise ValueError("aucun texte exploitable (PDF scanne ?)")
        lots = _lots(pages, numeros)
        _maj(travail_id, etape="Lecture des pages utiles", total=len(lots) + 1)
        points: list[dict] = []
        for i, lot in enumerate(lots):
            # Pas de format JSON impose ici : sur de longs extraits, les modeles l'ignorent souvent
            # (qwen3.5 repond en liste a puces). Une ligne par point se relit de facon fiable.
            reponse = ollama.discuter(modele, [
                {"role": "system", "content": PRUDENCE},
                {"role": "user", "content":
                    f"Extrait du rapport annuel de {societe}. Releve les points importants pour un actionnaire de long "
                    "terme : risques, strategie, perspectives, et tout signe de rupture (changement de metier, "
                    "acquisition ou cession majeure, restructuration, depreciation, litige, changement de direction). "
                    "Au plus 8 points. Une ligne par point, exactement sous cette forme :\n"
                    "- [risque|strategie|perspective|rupture] (p. NUMERO) phrase courte\n\n" + lot}])
            points += lire_points(reponse)
            _maj(travail_id, fait=i + 1)
        _maj(travail_id, etape="Synthèse")
        points = _trier(points)
        synthese = None
        with contextlib.suppress(ollama.OllamaIndisponible):
            synthese = _synthetiser(modele, societe, points)
        if synthese is None:                              # on garde au moins les points releves
            synthese = {"resume": "Synthèse impossible : voici les points relevés page par page.",
                        "risques": [], "strategie": [], "perspectives": [], "signaux_rupture": [], "questions": []}
        synthese |= {"pages_lues": numeros, "pages_total": len(pages), "points": points}
        analyse_id = _enregistrer(valeur_id, "rapport", nom, modele, debut, synthese)
        _maj(travail_id, etape="Terminé", fait=len(lots) + 1, termine=True, analyse_id=analyse_id)
    except Exception as e:
        _maj(travail_id, termine=True, erreur=str(e))


_PAGE = re.compile(r"\(?\s*(?:p\.|pages?)\s*(\d{1,4})", re.I)
_CATEGORIE = re.compile(r"\[\s*(risques?|strat[ée]gie|perspectives?|rupture)\s*\]", re.I)
_DEVINE = [("rupture", ("cession", "acquisition", "restructur", "dépréciation", "litige", "rupture", "scission")),
           ("perspective", ("perspective", "objectif", "prévoi", "guidance", "2025", "2026", "2027", "2030")),
           ("strategie", ("stratég", "ambition", "priorit", "investi", "développ")),
           ("risque", ("risque",))]


def lire_points(reponse: str) -> list[dict]:
    """Points d'un lot : JSON si le modele en a produit, sinon une ligne par point (- [cat] (p. 12) texte)."""
    with contextlib.suppress(ValueError, AttributeError):
        return [p for p in ollama.json_tolerant(reponse).get("points", []) if p.get("texte")]
    points = []
    for ligne in reponse.splitlines():
        ligne = ligne.strip()
        if not re.match(r"^([-*•]|\d+[.)])\s+", ligne):
            continue
        texte = re.sub(r"^([-*•]|\d+[.)])\s+", "", ligne)
        page = _PAGE.search(texte)
        categorie = _CATEGORIE.search(texte)
        texte = _CATEGORIE.sub("", _PAGE.sub("", texte)).replace("**", "").strip(" :-–)(.")
        if len(texte) < 15:
            continue
        if categorie:
            cle = categorie.group(1).lower()
            nom = "risque" if cle.startswith("risque") else "strategie" if cle.startswith("strat") else \
                "perspective" if cle.startswith("perspective") else "rupture"
        else:
            nom = next((c for c, mots in _DEVINE if any(m in texte.lower() for m in mots)), "risque")
        points.append({"categorie": nom, "texte": texte + ".", "page": int(page.group(1)) if page else None})
    return points


def _trier(points: list[dict]) -> list[dict]:
    """Sans doublon, textes courts, ruptures et risques d'abord (ce sont eux qu'on ne veut pas perdre)."""
    ordre = {"rupture": 0, "risque": 1, "strategie": 2, "perspective": 3}
    vus, resultat = set(), []
    for p in sorted(points, key=lambda p: ordre.get(str(p.get("categorie")), 4)):
        texte = str(p["texte"]).strip()[:220]
        if texte.lower() not in vus:
            vus.add(texte.lower())
            resultat.append({**p, "texte": texte})
    return resultat


def _synthetiser(modele: str, societe: str, points: list[dict]) -> dict:
    """Listes construites directement a partir des points (pages comprises) ; le modele ecrit
    seulement le resume et les questions a verifier, en texte simple."""
    par_categorie: dict[str, list[dict]] = {c: [] for c in CATEGORIES}
    for p in points:
        par_categorie.get(p.get("categorie") or "risque", par_categorie["risque"]).append(
            {"texte": p["texte"], "pages": [p["page"]] if p.get("page") else []})
    liste = "\n".join(f"- {p['texte']}" for p in points[:POINTS_MAX])
    resume = ollama.discuter(modele, [
        {"role": "system", "content": PRUDENCE},
        {"role": "user", "content": f"Points releves dans le rapport annuel de {societe}. Resume-les en 5 lignes "
                                    "de texte simple, sans liste ni titre.\n\n" + liste}]).strip()
    questions = [re.sub(r"^([-*•]|\d+[.)])\s+", "", l.strip()) for l in ollama.discuter(modele, [
        {"role": "system", "content": PRUDENCE},
        {"role": "user", "content": f"A partir de ces points du rapport annuel de {societe}, ecris 3 a 5 questions "
                                    "qu'un actionnaire devrait verifier lui-meme dans le document. Une question par "
                                    "ligne, commencant par « - ».\n\n" + liste}]).splitlines()
                 if re.match(r"^([-*•]|\d+[.)])\s+", l.strip())]
    return {"resume": resume, "risques": par_categorie["risque"][:8], "strategie": par_categorie["strategie"][:8],
            "perspectives": par_categorie["perspective"][:8], "signaux_rupture": par_categorie["rupture"][:8],
            "questions": questions[:5]}


# ── Questions sur la fiche ─────────────────────────────────────────────
def _arrondi(objet):
    if isinstance(objet, float):
        return float(f"{objet:.4g}")
    if isinstance(objet, dict):
        return {k: _arrondi(v) for k, v in objet.items() if v is not None}
    if isinstance(objet, list):
        return [_arrondi(v) for v in objet]
    return objet


def contexte(db: Session, valeur_id: int) -> dict:
    """Les chiffres deja calcules, en version compacte (quelques milliers de jetons au plus)."""
    from backend.services.analyse_service import AnalyseService
    a = AnalyseService(db).analyse(valeur_id)
    v = a["valeur"]
    resume: dict = {"valeur": {k: v.get(k) for k in ("nom", "symbole", "type", "secteur", "pays", "devise")},
                    "cours": a.get("stats"), "signaux_techniques": [s.get("texte") for s in a.get("signaux", [])]}
    if reg := a.get("regression"):
        resume["droite_de_regression"] = {k: reg.get(k) for k in (
            "pente", "ecart_type", "position", "zone_libelle", "annees", "debut", "fin", "retour_droite", "valeur_droite")}
    if fia := a.get("fiabilite"):
        details = [f"{x['titre']} : {x['statut']} — {x['texte']}" for x in fia["verifications"]]
        resume["trois_verifications"] = {"verdict": fia["verdict"]["texte"], "details": details}
    if b := a.get("benefices"):
        resume["benefices"] = {"per_actuel": b.get("per_actuel"), "per_median": b.get("per_median"),
                               "ecart_au_per_median": b.get("ecart_per_median"),
                               "pente_bpa": (b.get("droite_bpa") or {}).get("pente")}
    if c := a.get("comptes"):
        resume["qualite"] = {"note_sur_100": c["note"]["note"], "synthese": c["synthese"],
                             "criteres_note": [f"{x['nom']} : " + (f"{x['points']}/{x['plafond']}" if x["points"] is not None
                                                                   else "non calculé (donnée manquante)")
                                               for x in c["note"]["criteres"]],
                             "piotroski": c["piotroski"][-1]["score"] if c["piotroski"] else None,
                             "altman": (c.get("altman") or [{}])[-1].get("z") if isinstance(c.get("altman"), list)
                             else (c.get("altman") or {}).get("z"),
                             "beneish": c["beneish"][-1]["m"] if c["beneish"] else None}
        resume["ratios_annuels"] = [{k: r.get(k) for k in ("annee", "marge_operationnelle", "marge_nette", "roic",
                                                           "dette_nette_ebitda", "conversion_fcf", "dilution")}
                                    for r in c["ratios"][-6:]]
    resume["comptes_annuels"] = [{k: f.get(k) for k in ("annee", "chiffre_affaires", "benefice_net", "bpa", "dividende",
                                                        "flux_operationnel", "capex", "dette_financiere", "tresorerie")}
                                 for f in a.get("fondamentaux", [])[-6:]]
    if (valo := a.get("valorisation")) and "multiples" in valo:
        resume["valorisation"] = {
            "multiples_actuels": valo["multiples"].get("actuels"),
            "cherte_historique_0_a_1": {k: h.get("cherte") for k, h in valo["multiples"].get("historique", {}).items()},
            "modeles": [{"nom": m.get("nom"), "valeur": m.get("valeur"), "marge_securite": m.get("marge_securite")}
                        for m in valo["modeles"].get("modeles", [])],
            "dcf_inverse": valo["modeles"].get("dcf_inverse")}
    return _arrondi(resume)


def repondre(db: Session, valeur_id: int, question: str, historique: list[dict]):
    modele = _modele()
    donnees = json.dumps(contexte(db, valeur_id), ensure_ascii=False)
    messages = [
        {"role": "system", "content": PRUDENCE + " Les donnees de la fiche (calculees par l'application, en JSON) "
         "suivent. Les pourcentages sont en fraction (0,12 = 12 %). Explique simplement, en citant les chiffres "
         "utilises ; reponds en quelques paragraphes courts.\n\n" + donnees},
        *[{"role": m["role"], "content": m["contenu"]} for m in historique[-6:] if m.get("role") in ("user", "assistant")],
        {"role": "user", "content": question},
    ]
    return ollama.flux(modele, messages)


# ── Actualites ─────────────────────────────────────────────────────────
def lire_actualites(reponse: str) -> dict:
    """Relit la reponse balisee (SYNTHESE / TON GENERAL / - [ton] fait / A VERIFIER), avec tolerance."""
    sans_gras = reponse.replace("**", "")
    def apres(etiquette: str) -> str:
        m = re.search(rf"^\W*{etiquette}\W*:\s*(.+?)(?=^\W*(?:SYNTH|TON G|A V[ÉE]RIF|-\s*\[)|\Z)", sans_gras, re.I | re.M | re.S)
        return " ".join(m.group(1).split()) if m else ""
    ton = apres("TON G[ÉE]N[ÉE]RAL").lower()
    points = []
    for m in re.finditer(r"^\s*[-*•]\s*\[\s*(positif|n[ée]gatif|neutre)\s*\]\s*(.+)$", sans_gras, re.I | re.M):
        points.append({"texte": m.group(2).strip(), "ton": {"negatif": "négatif"}.get(m.group(1).lower(), m.group(1).lower())})
    return {"synthese": apres("SYNTH[ÈE]SE") or sans_gras.strip()[:600],
            "points": points,
            "ton_general": next((t for t in TONS if t.split()[-1][:5] in ton), "neutre"),
            "a_verifier": [x.strip() for x in apres("A V[ÉE]RIFIER").split(";") if x.strip()]}


def resumer_actualites(db: Session, valeur_id: int) -> dict:
    from backend.sources import actualites as source
    valeur = _valeur(db, valeur_id)
    modele = _modele()
    articles = source.actualites(valeur.nom, valeur.symbole, nombre=25)
    if not articles:
        raise HTTPException(404, "Aucune actualité récente trouvée pour cette valeur.")
    debut = time.monotonic()
    titres = "\n".join(f"- {(a.get('moment') or '')[:10]} · {a.get('source') or '?'} : {a['titre']}" for a in articles)
    resultat = lire_actualites(ollama.discuter(modele, [
        {"role": "system", "content": PRUDENCE},
        {"role": "user", "content":
            f"Titres d'actualite recents sur {valeur.nom} (seulement les titres, pas les articles). Ignore les titres "
            "sans rapport avec l'entreprise. Reponds exactement sous cette forme :\n"
            "SYNTHESE : trois lignes de texte simple\n"
            "TON GENERAL : plutôt positif, plutôt négatif, neutre ou partagé\n"
            "- [positif|négatif|neutre] un fait marquant (3 a 6 lignes de ce type)\n"
            "A VERIFIER : ce qu'un actionnaire devrait aller verifier, separe par des points-virgules\n\n" + titres}]))
    resultat["articles"] = articles
    titre = f"Actualités du {datetime.now(UTC):%d/%m/%Y}"
    resultat["id"] = _enregistrer(valeur_id, "actualites", titre, modele, debut, resultat)
    return resultat
