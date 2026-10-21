"""Import d'un releve d'operations de courtier (CSV), en deux temps : proposition, puis validation.

Les courtiers ont chacun leur format ; on reconnait les colonnes par leur nom (Boursorama,
Degiro, Fortuneo, Trade Republic, Bourse Direct… et les intitules usuels en francais et en
anglais), le type d'operation par mots-cles (ou par le signe de la quantite, comme chez
Degiro), et la valeur par son ISIN ou son symbole. Rien n'est enregistre avant relecture.
"""
import re

import pandas as pd
from fastapi import HTTPException
from sqlmodel import Session, select

from backend.db.schema import Valeur
from backend.models.portefeuille import TransactionEcriture
from backend.services.import_service import _associer, _dates, _lire, _nombres, _normaliser
from backend.services.portefeuille_service import PortefeuilleService
from backend.sources import yahoo
from backend.sources.base import SourceIndisponible

COLONNES = {
    "jour":     ["date", "dateoperation", "datedoperation", "dateexecution", "datevaleur", "jour", "tradedate"],
    "type":     ["type", "sens", "operation", "typeoperation", "nature", "naturedeloperation", "action", "transaction"],
    "isin":     ["isin", "codeisin", "codeisinproduit"],
    "symbole":  ["symbole", "ticker", "mnemo", "mnemonique", "code"],
    "libelle":  ["libelle", "produit", "valeur", "titre", "nom", "description", "instrument", "name"],
    "quantite": ["quantite", "qte", "nombre", "nombredetitres", "quantity", "shares", "parts"],
    "prix":     ["cours", "prix", "prixunitaire", "coursexecution", "price", "cours unitaire"],
    "frais":    ["frais", "fraisdecourtage", "commission", "courtage", "fees", "frais de transaction"],
    "montant":  ["montant", "montantnet", "net", "total", "montanteur", "valeurlocale", "amount", "montantnetdevisedecompte"],
}
TYPES = [
    ("achat", r"achat|buy|acquisition|souscription|purchase"),
    ("vente", r"vente|sell|cession|sale"),
    ("dividende", r"dividende|dividend|coupon|distribution"),
    ("depot", r"d[eé]p[oô]t|versement|deposit|virement (entrant|re[cç]u)|alimentation"),
    ("retrait", r"retrait|withdraw|virement (sortant|[eé]mis)"),
    ("frais", r"frais|commission|droits de garde|fee|ttf|taxe"),
    ("division", r"division|split|attribution gratuite"),
]
ISIN = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b")


def _type(texte: str, quantite: float | None) -> str | None:
    texte = (texte or "").lower()
    for nom, motif in TYPES:
        if re.search(motif, texte):
            return nom
    if quantite:                                    # Degiro : pas de colonne type, quantite signee
        return "achat" if quantite > 0 else "vente"
    return None


def proposer(db: Session, compte_id: int, contenu: bytes) -> dict:
    df = _lire(contenu)
    colonnes = _associer(df, {k: [_normaliser(n) for n in v] for k, v in COLONNES.items()})
    if "jour" not in colonnes:
        raise HTTPException(400, f"Colonne de date introuvable. Colonnes lues : {', '.join(map(str, df.columns))}.")

    jours = _dates(df[colonnes["jour"]])
    nombres = {c: _nombres(df[colonnes[c]]) for c in ("quantite", "prix", "frais", "montant") if c in colonnes}
    valeurs = list(db.exec(select(Valeur)))
    par_isin = {v.isin.upper(): v for v in valeurs if v.isin}
    par_symbole = {v.symbole.upper(): v for v in valeurs}

    lignes = []
    for i in range(len(df)):
        if pd.isna(jours.iloc[i]):
            continue
        brut = {c: (None if pd.isna(s.iloc[i]) else float(s.iloc[i])) for c, s in nombres.items()}
        texte = " ".join(str(df.iloc[i][colonnes[c]]) for c in ("type", "libelle") if c in colonnes)
        quantite = brut.get("quantite")
        type_ = _type(str(df.iloc[i][colonnes["type"]]) if "type" in colonnes else texte, quantite)
        isin = None
        if "isin" in colonnes and isinstance(df.iloc[i][colonnes["isin"]], str):
            isin = df.iloc[i][colonnes["isin"]].strip().upper() or None
        isin = isin or (m.group() if (m := ISIN.search(texte.upper())) else None)
        symbole = str(df.iloc[i][colonnes["symbole"]]).strip().upper() if "symbole" in colonnes else None
        libelle = str(df.iloc[i][colonnes["libelle"]]).strip() if "libelle" in colonnes else texte.strip()
        valeur = (par_isin.get(isin) if isin else None) or (par_symbole.get(symbole) if symbole else None)

        lignes.append({
            "jour": jours.iloc[i].isoformat(), "type": type_, "libelle": libelle[:120], "isin": isin,
            "symbole": symbole, "valeur_id": valeur.id if valeur else None, "valeur_nom": valeur.nom if valeur else None,
            "quantite": abs(quantite) if quantite is not None else None,
            "prix": abs(brut["prix"]) if brut.get("prix") is not None else None,
            "frais": abs(brut["frais"]) if brut.get("frais") is not None else None,
            "montant": abs(brut["montant"]) if brut.get("montant") is not None else None,
        })
    if not lignes:
        raise HTTPException(400, "Aucune opération lisible dans le fichier.")

    # Valeurs inconnues : suggestion Yahoo par ISIN (une recherche par ISIN distinct).
    suggestions = {}
    for isin in {l["isin"] for l in lignes if l["isin"] and not l["valeur_id"]}:
        try:
            trouves = yahoo.rechercher(isin, nombre=3)
        except SourceIndisponible:
            trouves = []
        if trouves:
            suggestions[isin] = trouves[0]
    for l in lignes:
        if not l["valeur_id"] and l["isin"] in suggestions:
            l["suggestion"] = suggestions[l["isin"]]
    return {"compte_id": compte_id, "colonnes": colonnes, "lignes": lignes}


def valider(db: Session, compte_id: int, lignes: list[dict]) -> dict:
    """Cree les valeurs suggerees manquantes (sans attendre leur telechargement), puis les operations."""
    from backend.models.valeur import ValeurCreate
    from backend.services.valeur_service import ValeurService

    service, valeurs = PortefeuilleService(db), ValeurService(db)
    crees, ignorees = 0, 0
    for l in lignes:
        if not l.get("type"):
            ignorees += 1
            continue
        if not l.get("valeur_id") and l.get("suggestion") and l["type"] in ("achat", "vente", "dividende", "division"):
            existante = db.exec(select(Valeur).where(Valeur.symbole == l["suggestion"]["symbole"])).first()
            if existante is None:
                existante_id = valeurs.create(ValeurCreate(symbole=l["suggestion"]["symbole"]), actualiser=False).id
                existante = db.get(Valeur, existante_id)
            if l.get("isin") and not existante.isin:
                existante.isin = l["isin"]
            l["valeur_id"] = existante.id
        try:
            service.ecrire_transaction(TransactionEcriture(
                compte_id=compte_id, valeur_id=l.get("valeur_id"), jour=l["jour"], type=l["type"],
                quantite=l.get("quantite"), prix=l.get("prix"), frais=l.get("frais"),
                montant=l.get("montant"), note=(l.get("libelle") or "")[:500] or None,
            ), commit=False)
            crees += 1
        except HTTPException:
            ignorees += 1
    db.commit()
    return {"crees": crees, "ignorees": ignorees,
            "message": f"{crees} opération(s) importée(s)" + (f", {ignorees} ignorée(s)." if ignorees else ".")}
