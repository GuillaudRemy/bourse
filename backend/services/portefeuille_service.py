"""Portefeuille : comptes, transactions, positions, performance, risque et fiscalite."""
from collections import defaultdict
from datetime import date

import pandas as pd
from fastapi import HTTPException
from sqlmodel import Session, select

from backend.analyse import portefeuille as pf
from backend.analyse.regression import ajuster, zone
from backend.core import reglages
from backend.db.schema import Compte, Transaction, Valeur
from backend.models.portefeuille import CompteEcriture, CompteRead, TransactionEcriture, TransactionRead
from backend.services.stockage import charger_cours, charger_divisions, charger_taux, enregistrer_taux
from backend.sources import bce
from backend.sources.base import SourceIndisponible
from backend.sources.esef import PAYS_EUROPE

PLAFONDS = {"PEA": 150_000, "PEA-PME": 225_000}     # PEA-PME : plafond commun avec le PEA
FLAT_TAX = 0.30                                      # 12,8 % d'impot + 17,2 % de prelevements sociaux


class PortefeuilleService:
    def __init__(self, session: Session):
        self._db = session
        self._prix_cache: dict[int, pd.Series] = {}

    # ── Comptes ──
    def comptes(self) -> list[CompteRead]:
        return [CompteRead.model_validate(c) for c in self._db.exec(select(Compte).order_by(Compte.nom))]

    def ecrire_compte(self, data: CompteEcriture, compte_id: int | None = None) -> CompteRead:
        compte = self._compte(compte_id) if compte_id else Compte()
        for cle, v in data.model_dump().items():
            setattr(compte, cle, v)
        self._db.add(compte)
        self._db.commit()
        self._db.refresh(compte)
        return CompteRead.model_validate(compte)

    def supprimer_compte(self, compte_id: int) -> None:
        self._db.delete(self._compte(compte_id))
        self._db.commit()

    # ── Transactions ──
    def transactions(self, compte_id: int | None = None) -> list[TransactionRead]:
        requete = select(Transaction).order_by(Transaction.jour.desc(), Transaction.id.desc())
        if compte_id:
            requete = requete.where(Transaction.compte_id == compte_id)
        return [TransactionRead.model_validate(t) for t in self._db.exec(requete)]

    def ecrire_transaction(self, data: TransactionEcriture, transaction_id: int | None = None,
                           commit: bool = True) -> TransactionRead:
        self._compte(data.compte_id)
        valeur = self._db.get(Valeur, data.valeur_id) if data.valeur_id else None
        if data.valeur_id and not valeur:
            raise HTTPException(404, "Valeur introuvable.")
        if data.type in ("achat", "vente", "division", "dividende") and not valeur:
            raise HTTPException(422, "Cette opération doit porter sur une valeur.")
        if data.type in ("achat", "vente") and (not data.quantite or data.prix is None):
            raise HTTPException(422, "Un achat ou une vente demande une quantité et un prix.")
        if data.type in ("dividende", "depot", "retrait") and data.montant is None:
            raise HTTPException(422, "Indiquez le montant en euros.")

        champs = data.model_dump()
        champs["montant"] = self._montant(data, valeur)
        t = self._db.get(Transaction, transaction_id) if transaction_id else Transaction(**champs)
        if transaction_id and not t:
            raise HTTPException(404, "Opération introuvable.")
        for cle, v in champs.items():
            setattr(t, cle, v)
        self._db.add(t)
        if commit:
            self._db.commit()
            self._db.refresh(t)
        else:
            self._db.flush()
        return TransactionRead.model_validate(t)

    def supprimer_transaction(self, transaction_id: int) -> None:
        t = self._db.get(Transaction, transaction_id)
        if not t:
            raise HTTPException(404, "Opération introuvable.")
        self._db.delete(t)
        self._db.commit()

    def _montant(self, data: TransactionEcriture, valeur: Valeur | None) -> float:
        """Flux de tresorerie en euros, signe du point de vue du compte."""
        if data.type in ("achat", "vente"):
            brut = data.quantite * data.prix / self._taux(valeur.devise if valeur else "EUR", data.jour)
            if data.montant is not None:                     # montant reel du releve : prioritaire
                return -abs(data.montant) if data.type == "achat" else abs(data.montant)
            return -(brut + data.frais) if data.type == "achat" else brut - data.frais
        if data.type in ("frais", "retrait"):
            return -abs(data.montant if data.montant is not None else data.frais)
        if data.type == "division":
            return 0.0
        return abs(data.montant)                              # dividende, depot

    def _taux(self, devise_brute: str | None, jour: date) -> float:
        """Unites de devise pour 1 euro au jour donne (dernier taux connu) ; sous-unites (pence) incluses."""
        devise, diviseur = bce.normaliser(devise_brute)
        if not devise or devise == "EUR":
            return diviseur
        taux = charger_taux(self._db, devise)
        if taux.empty or taux.index.max() < pd.Timestamp(jour):
            try:
                enregistrer_taux(self._db, devise, bce.taux(devise))
                taux = charger_taux(self._db, devise)
            except SourceIndisponible as e:
                if taux.empty:
                    raise HTTPException(502, f"Taux {devise}/EUR indisponible : {e}") from e
        avant = taux[taux.index <= pd.Timestamp(jour)]
        return float((avant.iloc[-1] if len(avant) else taux.iloc[0]) * diviseur)

    def _prix_eur(self, valeur: Valeur, ajuste: bool = False) -> pd.Series:
        if (valeur.id, ajuste) in self._prix_cache:
            return self._prix_cache[valeur.id, ajuste]
        cours = charger_cours(self._db, valeur.id)
        if cours.empty:
            return pd.Series(dtype=float)
        serie = (cours["ajuste"] if ajuste and cours["ajuste"].notna().mean() > 0.9 else cours["cloture"]).dropna()
        devise, diviseur = bce.normaliser(valeur.devise)
        if devise and devise != "EUR":
            taux = charger_taux(self._db, devise)
            if taux.empty:
                self._taux(valeur.devise, date.today())
                taux = charger_taux(self._db, devise)
            taux = taux.reindex(serie.index.union(taux.index)).ffill().reindex(serie.index)
            serie = (serie / diviseur / taux).dropna()
        elif diviseur != 1:
            serie = serie / diviseur
        self._prix_cache[valeur.id, ajuste] = serie
        return serie

    # ── Vue d'ensemble ──
    def synthese(self, compte_id: int | None = None) -> dict:
        comptes = {c.id: c for c in self._db.exec(select(Compte))}
        requete = select(Transaction)
        if compte_id:
            self._compte(compte_id)
            requete = requete.where(Transaction.compte_id == compte_id)
        transactions = [t.model_dump() for t in self._db.exec(requete)]
        if not transactions:
            return {"vide": True, "comptes": [CompteRead.model_validate(c).model_dump() for c in comptes.values()]}

        valeurs = {v.id: v for v in self._db.exec(select(Valeur).where(
            Valeur.id.in_({t["valeur_id"] for t in transactions if t["valeur_id"]})))}
        prix = {vid: self._prix_eur(v) for vid, v in valeurs.items()}
        divisions = {vid: charger_divisions(self._db, vid) for vid in valeurs}
        lignes = pf.positions(transactions, divisions)

        positions = []
        for vid, l in lignes.items():
            v = valeurs.get(vid)
            if not v:
                continue
            serie = prix.get(vid, pd.Series(dtype=float))
            cours_eur = float(serie.iloc[-1]) if len(serie) else None
            valeur_actuelle = cours_eur * l.quantite if cours_eur is not None and l.quantite > 1e-9 else 0.0
            latente = valeur_actuelle - l.cout if l.quantite > 1e-9 else 0.0
            veille = float(serie.iloc[-2]) if len(serie) > 1 else None
            positions.append({
                "valeur_id": vid, "nom": v.nom, "symbole": v.symbole, "type": v.type, "secteur": v.secteur,
                "pays": v.pays, "devise": v.devise, "quantite": l.quantite, "pru": l.pru, "cout": l.cout,
                "cours_eur": cours_eur, "valeur_actuelle": valeur_actuelle,
                "variation_jour": (cours_eur / veille - 1) if cours_eur and veille else None,
                "plus_value_latente": latente, "plus_value_latente_pct": latente / l.cout if l.cout > 0 else None,
                "plus_value_realisee": l.plus_value_realisee, "dividendes": l.dividendes, "frais": l.frais,
                "eligible_pea": _eligible_pea(v), **self._couloir(v),
            })
        ouvertes = [p for p in positions if p["quantite"] > 1e-9]
        total_titres = sum(p["valeur_actuelle"] for p in ouvertes)
        for p in positions:
            p["poids"] = p["valeur_actuelle"] / total_titres if total_titres and p["quantite"] > 1e-9 else 0.0

        quotidien = pf.valeur_quotidienne(transactions, prix, divisions)
        performance = self._performance(quotidien)
        poids = sorted((p["poids"] for p in ouvertes), reverse=True)
        return {
            "vide": False,
            "comptes": [CompteRead.model_validate(c).model_dump() for c in comptes.values()],
            "positions": sorted(positions, key=lambda p: -p["valeur_actuelle"]),
            "totaux": {
                "valeur_titres": total_titres,
                "especes": float(quotidien["especes"].iloc[-1]) if len(quotidien) else 0.0,
                "valeur": float(quotidien["valeur"].iloc[-1]) if len(quotidien) else total_titres,
                "cout": sum(p["cout"] for p in ouvertes),
                "plus_value_latente": sum(p["plus_value_latente"] for p in ouvertes),
                "plus_value_realisee": sum(p["plus_value_realisee"] for p in positions),
                "dividendes": sum(p["dividendes"] for p in positions),
                "frais": sum(p["frais"] for p in positions),
                "variation_jour": _variation_jour(quotidien),
            },
            "concentration": {"premiere": poids[0] if poids else None, "cinq_premieres": sum(poids[:5]) if poids else None,
                              "lignes": len(ouvertes)},
            "repartitions": {cle: pf.repartition(ouvertes, cle) for cle in ("secteur", "pays", "devise", "type")},
            "performance": performance,
            "correlations": {**pf.correlations({p["valeur_id"]: prix[p["valeur_id"]] for p in ouvertes}),
                             "noms": {p["valeur_id"]: p["nom"] for p in ouvertes}},
            "fiscalite": self._fiscalite(transactions, divisions, comptes),
        }

    def _performance(self, quotidien: pd.DataFrame) -> dict:
        if quotidien.empty:
            return {}
        cumul = pf.twr(quotidien)
        annees = max((quotidien.index[-1] - quotidien.index[0]).days / 365.25, 1 / 365)
        resultat = {
            "twr": float(cumul.iloc[-1]),
            "twr_annualise": float((1 + cumul.iloc[-1]) ** (1 / annees) - 1) if annees >= 1 else None,
            "xirr": pf.xirr(pf.flux_investisseur(quotidien)),
            "apports_nets": float(quotidien["flux"].sum()),
        }
        ref_cumul = None
        symbole = reglages.lire("indice_reference")
        ref = self._db.exec(select(Valeur).where(Valeur.symbole == symbole)).first() if symbole else None
        if ref:
            prix_ref = self._prix_eur(ref, ajuste=True)
            if len(prix_ref):
                q_ref = pf.reference(quotidien, prix_ref)
                ref_cumul = pf.twr(q_ref)
                resultat["reference"] = {"nom": ref.nom, "symbole": ref.symbole, "twr": float(ref_cumul.iloc[-1]),
                                         "xirr": pf.xirr(pf.flux_investisseur(q_ref)),
                                         "valeur": float(q_ref["valeur"].iloc[-1])}
        else:
            resultat["reference"] = {"manquante": symbole}
        hebdo = quotidien.resample("W").last().index
        resultat["serie"] = {
            "jours": [j.strftime("%Y-%m-%d") for j in hebdo],
            "portefeuille": [round(float(v), 5) for v in cumul.reindex(hebdo, method="ffill")],
            "reference": None if ref_cumul is None
            else [round(float(v), 5) for v in ref_cumul.reindex(hebdo, method="ffill")],
            "valeur": [round(float(v), 2) for v in quotidien["valeur"].reindex(hebdo, method="ffill")],
        }
        resultat["risque"] = pf.risque(cumul, ref_cumul)
        return resultat

    def _couloir(self, valeur: Valeur) -> dict:
        cours = charger_cours(self._db, valeur.id)
        if cours.empty:
            return {"position": None, "zone": None}
        base = (cours["ajuste"] if cours["ajuste"].notna().mean() > 0.9 else cours["cloture"]).dropna()
        reg = ajuster(base[base.index >= base.index[-1] - pd.DateOffset(years=23)])
        return {"position": reg.position, "zone": zone(reg.position)[0]} if reg else {"position": None, "zone": None}

    def _fiscalite(self, transactions: list[dict], divisions: dict, comptes: dict) -> dict:
        par_compte = defaultdict(list)
        for t in transactions:
            par_compte[t["compte_id"]].append(t)
        resultat = []
        for cid, ts in par_compte.items():
            compte = comptes.get(cid)
            if not compte:
                continue
            fiche = {"compte_id": cid, "nom": compte.nom, "type": compte.type}
            if compte.type in PLAFONDS:
                depots = sum(t["montant"] for t in ts if t["type"] == "depot") - \
                    sum(-t["montant"] for t in ts if t["type"] == "retrait")
                if not any(t["type"] in ("depot", "retrait") for t in ts):
                    depots = sum(-t["montant"] for t in ts if t["type"] == "achat") - \
                        sum(t["montant"] for t in ts if t["type"] == "vente")
                ouverture = compte.ouverture or min(t["jour"] for t in ts)
                anciennete = (date.today() - ouverture).days / 365.25
                ids = {t["valeur_id"] for t in ts if t["valeur_id"]}
                non_eligibles = [v.nom for v in self._db.exec(select(Valeur).where(Valeur.id.in_(ids)))
                                 if _eligible_pea(v) is False]
                fiche |= {"versements": depots, "plafond": PLAFONDS[compte.type],
                          "reste": PLAFONDS[compte.type] - depots, "ouverture": ouverture.isoformat(),
                          "anciennete": anciennete, "cinq_ans": anciennete >= 5, "non_eligibles": non_eligibles}
            elif compte.type == "CTO":
                annees = defaultdict(lambda: {"plus_values": 0.0, "moins_values": 0.0, "dividendes": 0.0})
                for l in pf.positions(ts, divisions).values():
                    for jour, pv in l.ventes:
                        annees[jour.year]["plus_values" if pv >= 0 else "moins_values"] += pv
                for t in ts:
                    if t["type"] == "dividende":
                        annees[t["jour"].year]["dividendes"] += t["montant"]
                fiche["annees"] = [
                    {"annee": a, **v, "base": max(v["plus_values"] + v["moins_values"], 0) + v["dividendes"],
                     "impot_estime": FLAT_TAX * (max(v["plus_values"] + v["moins_values"], 0) + v["dividendes"]),
                     "moins_values_reportables": min(v["plus_values"] + v["moins_values"], 0)}
                    for a, v in sorted(annees.items(), reverse=True)
                ]
            resultat.append(fiche)
        return {"comptes": resultat, "flat_tax": FLAT_TAX}

    def _compte(self, compte_id: int) -> Compte:
        compte = self._db.get(Compte, compte_id)
        if not compte:
            raise HTTPException(404, "Compte introuvable.")
        return compte


def _eligible_pea(valeur: Valeur) -> bool | None:
    """Actions de societes de l'Union europeenne (ou EEE) : eligibles. ETF : a verifier (label PEA)."""
    if valeur.type != "action":
        return None
    if not valeur.pays:
        return None
    return valeur.pays in PAYS_EUROPE


def _variation_jour(quotidien: pd.DataFrame) -> float | None:
    if len(quotidien) < 2:
        return None
    v, veille, flux = quotidien["valeur"].iloc[-1], quotidien["valeur"].iloc[-2], quotidien["flux"].iloc[-1]
    return float((v - flux) / veille - 1) if veille > 0 else None
