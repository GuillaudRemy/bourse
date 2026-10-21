"""Assemble l'analyse complete d'une valeur : series pour les graphiques,
droite de regression, indicateurs techniques, fiabilite et fondamentaux."""
import json
import math
from datetime import date

import pandas as pd
from fastapi import HTTPException
from sqlmodel import Session, select

from backend.analyse import benefices, fiabilite, indices, projection, qualite, ratios, robustesse, scores
from backend.analyse import indicateurs as ind
from backend.analyse import valorisation as valo
from backend.analyse.regression import THEORIE, ZONES, ajuster, zone
from backend.core.config import config
from backend.db.schema import Valeur
from backend.models.valeur import ValeurRead
from backend.services import cache
from backend.services.stockage import charger_cours, charger_fondamentaux, charger_taux
from backend.sources import bce

PROJECTION_ANS = 3


def _liste(serie, decimales: int = 4) -> list:
    """Serie -> liste JSON (NaN -> null)."""
    return [None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), decimales)
            for v in serie]


def _f(v):
    return None if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else float(v)


# Secteurs aux cycles plus longs que les autres (banques, defense) : la droite part plus tot,
# comme pour les indices, afin de couvrir plusieurs cycles complets.
SECTEURS_CYCLES_LONGS = {"Financial Services"}
INDUSTRIES_CYCLES_LONGS = {"Banks - Diversified", "Banks - Regional", "Aerospace & Defense", "Insurance - Diversified",
                           "Insurance - Life", "Insurance - Property & Casualty"}


def debut_par_defaut(valeur: Valeur) -> tuple[date, str]:
    """Date de depart par defaut de la droite, et sa justification."""
    if valeur.type == "indice":
        return date(config.DEBUT_INDICES, 1, 1), "début du régime monétaire moderne"
    industrie = json.loads(valeur.infos).get("industrie") if valeur.infos else None
    if valeur.secteur in SECTEURS_CYCLES_LONGS or industrie in INDUSTRIES_CYCLES_LONGS:
        return date(config.DEBUT_INDICES, 1, 1), "secteur aux cycles longs (banque, assurance, défense)"
    return date(config.DEBUT_ACTIONS, 1, 1), "après la bulle internet et l'entrée de la Chine à l'OMC"


class AnalyseService:
    def __init__(self, session: Session):
        self._db = session

    def _contexte(self, valeur_id: int, dividendes: bool, debut: date | None, en_euros: bool = False):
        valeur = self._db.get(Valeur, valeur_id)
        if not valeur:
            raise HTTPException(404, "Valeur introuvable.")
        cours = charger_cours(self._db, valeur_id)
        # Les comptes (PER) restent dans leur devise : on garde la cloture d'origine pour eux.
        self._cloture_origine = cours["cloture"] if not cours.empty else pd.Series(dtype=float)
        self._devise = valeur.devise
        if en_euros and not cours.empty:
            cours = self._en_euros(cours, valeur.devise)
        if cours.empty:
            return valeur, cours, None, None, None

        # Base de la droite : rendement total si disponible, sinon cloture.
        base_ajustee = bool(dividendes and cours["ajuste"].notna().mean() > 0.9)
        base = (cours["ajuste"] if base_ajustee else cours["cloture"]).dropna()

        debut = debut or valeur.debut_regression or debut_par_defaut(valeur)[0]
        fenetre = base[base.index >= pd.Timestamp(debut)]
        if len(fenetre) < 250:          # trop court depuis le debut choisi : tout l'historique
            fenetre = base
        return valeur, cours, base_ajustee, fenetre, ajuster(fenetre)

    def _en_euros(self, cours: pd.DataFrame, devise_brute: str | None) -> pd.DataFrame:
        """Cours convertis en euros au taux BCE du jour (le dernier connu les jours sans taux).
        Avant 1999 (pas de taux BCE), l'historique est coupe."""
        devise, diviseur = bce.normaliser(devise_brute)
        if not devise or devise == "EUR":
            return cours / diviseur if diviseur != 1 else cours
        taux = charger_taux(self._db, devise)
        if taux.empty:
            raise HTTPException(409, f"Taux {devise}/EUR absents : actualisez la valeur pour les télécharger.")
        taux = taux.reindex(cours.index.union(taux.index)).ffill().reindex(cours.index)
        converti = cours.copy()
        for colonne in ("ouverture", "haut", "bas", "cloture", "ajuste"):
            converti[colonne] = cours[colonne] / diviseur / taux
        self._devise = "EUR"
        return converti.dropna(subset=["cloture"])

    def _fondamentaux(self, valeur_id: int, cloture: pd.Series) -> list[dict]:
        fond = charger_fondamentaux(self._db, valeur_id)
        pers = fiabilite.per_annuels(cloture, fond) if not cloture.empty else {}
        for f in fond:
            f["per"] = pers.get(f["annee"])
        return fond

    # ── Fiche complete ────────────────────────────────────────────────
    def analyse(self, valeur_id: int, dividendes: bool = True, debut: date | None = None,
                en_euros: bool = False) -> dict:
        valeur, cours, base_ajustee, fenetre, reg = self._contexte(valeur_id, dividendes, debut, en_euros)
        resultat = {
            "valeur": ValeurRead.model_validate(valeur).model_dump(mode="json"),
            "debut_defaut": debut_par_defaut(valeur)[0].isoformat(),
            "debut_defaut_raison": debut_par_defaut(valeur)[1],
            # Un indice se lit en points, pas dans une devise (un ETF, lui, a bien un prix en euros).
            "devise_affichee": "pts" if valeur.type == "indice" else self._devise,
            "en_euros": en_euros,
            "vide": cours.empty,
        }
        if cours.empty:
            return resultat

        cloture = cours["cloture"]
        mm50, mm200 = ind.moyenne_mobile(cloture, 50), ind.moyenne_mobile(cloture, 200)
        rsi14 = ind.rsi(cloture)
        fondamentaux = self._fondamentaux(valeur_id, self._cloture_origine)

        resultat |= {
            "base_ajustee": base_ajustee,
            # Cours de cloture et rendement total pour la droite ; bougies et indicateurs : route /technique.
            "series": {
                "jours":   [d.strftime("%Y-%m-%d") for d in cours.index],
                "cloture": _liste(cloture),
                "ajuste":  _liste(cours["ajuste"]),
            },
            "stats": self._stats(cloture, mm50, mm200, rsi14),
            "signaux": ind.signaux(cloture, mm50, mm200, rsi14),
            "qualite": qualite.controler(cours),
            "avertissement_indice": indices.avertissement(valeur.symbole, valeur.nom, valeur.type),
            "fondamentaux": fondamentaux,
            "comptes": (comptes := self._comptes(valeur, fondamentaux)),
            "valorisation": self._valorisation(valeur, fondamentaux, comptes),
            "benefices": benefices.analyser(self._cloture_origine, fondamentaux),
        }

        if reg is None:
            resultat["regression"] = None
            return resultat

        resultat["regression"] = self._regression(reg, fenetre)
        resultat["projection"] = projection.analyser(reg, reg.fin)
        base = (cours["ajuste"] if base_ajustee else cours["cloture"]).dropna()
        coupure = robustesse.rupture(fenetre)
        resultat["robustesse"] = {
            "sensibilite": robustesse.sensibilite(base),
            "glissante": robustesse.pente_glissante(base),
            "rupture": coupure,
        }
        verifs = [
            fiabilite.historique(reg),
            fiabilite.per(reg, self._cloture_origine, fondamentaux),
            fiabilite.rupture(reg, fenetre, valeur.rupture, coupure),
        ]
        resultat["fiabilite"] = {"verifications": verifs, "verdict": fiabilite.verdict(verifs)}
        return resultat

    def _comptes(self, valeur: Valeur, fondamentaux: list[dict]) -> dict | None:
        """Ratios, synthese et scores, sur les annees qui ont au moins un poste du compte de resultat."""
        comptes = [f for f in fondamentaux
                   if f.get("chiffre_affaires") is not None or f.get("benefice_net") is not None]
        if not comptes:
            return None
        annuels = ratios.annuels(comptes)
        resume = ratios.synthese(comptes, annuels)
        piotroski = [scores.piotroski(comptes[i - 2] if i >= 2 else {}, comptes[i - 1], comptes[i])
                     for i in range(1, len(comptes))]
        beneish = [b for i in range(1, len(comptes)) if (b := scores.beneish(comptes[i - 1], comptes[i]))]
        return {
            "ratios": annuels,
            "synthese": resume,
            "note": scores.note_maison(resume),
            "piotroski": piotroski[-10:],
            "altman": self._altman(valeur, comptes),
            "beneish": beneish[-10:],
        }

    def _valorisation(self, valeur: Valeur, fondamentaux: list[dict], comptes: dict | None,
                      hypotheses: valo.Hypotheses | None = None) -> dict | None:
        """Multiples situes dans leur histoire, et modeles de valeur intrinseque. Calcules dans la
        devise des comptes ; si la cotation est dans une autre devise, les multiples seraient faux."""
        if comptes is None or self._cloture_origine.empty:
            return None
        if valeur.devise_comptes and valeur.devise and valeur.devise_comptes != valeur.devise:
            return {"indisponible": f"Cotation en {valeur.devise}, comptes en {valeur.devise_comptes} : "
                                    "multiples non calculés pour éviter un mélange de devises."}
        lignes = [f for f in fondamentaux if f.get("chiffre_affaires") is not None or f.get("benefice_net") is not None]
        cours = float(self._cloture_origine.iloc[-1])
        historique = valo.multiples_annuels(self._cloture_origine, lignes)
        hypotheses = hypotheses or valo.hypotheses_par_defaut(lignes, comptes["synthese"])
        return {
            "multiples": valo.situer(cours, lignes, historique),
            "historique": historique,
            "modeles": valo.modeles(cours, lignes, comptes["synthese"], hypotheses),
        }

    def valorisation(self, valeur_id: int, hypotheses: valo.Hypotheses) -> dict:
        """Recalcul des modeles avec les hypotheses choisies par l'utilisateur."""
        valeur, cours, *_ = self._contexte(valeur_id, True, None)
        fond = self._fondamentaux(valeur_id, self._cloture_origine)
        comptes = self._comptes(valeur, fond)
        resultat = self._valorisation(valeur, fond, comptes, hypotheses)
        if not resultat or "modeles" not in resultat:
            raise HTTPException(409, "Comptes insuffisants pour une valorisation.")
        return resultat["modeles"]

    def secteur(self, valeur_id: int) -> dict:
        """Multiples actuels des valeurs suivies du meme secteur, et leur mediane."""
        valeur = self._db.get(Valeur, valeur_id)
        if not valeur or not valeur.secteur:
            return {"secteur": None, "valeurs": [], "medianes": {}}
        lignes = []
        for autre in self._db.exec(select(Valeur).where(Valeur.secteur == valeur.secteur, Valeur.type == "action")):
            cloture = charger_cours(self._db, autre.id)["cloture"]
            fond = [f for f in charger_fondamentaux(self._db, autre.id) if f.get("chiffre_affaires") is not None]
            if cloture.empty or not fond:
                continue
            situation = valo.situer(float(cloture.iloc[-1]), fond, [])
            lignes.append({"id": autre.id, "nom": autre.nom, **situation.get("actuels", {})})
        medianes = {}
        for cle in valo.MULTIPLES:
            serie = [l[cle] for l in lignes if l.get(cle) is not None]
            if serie:
                medianes[cle] = float(pd.Series(serie).median())
        return {"secteur": valeur.secteur, "valeurs": lignes, "medianes": medianes}

    def _altman(self, valeur: Valeur, comptes: list[dict]) -> list[dict]:
        """La capitalisation (cours de fin d'annee x nombre d'actions) doit etre dans la devise des
        comptes : sinon le terme est inconnu plutot que faux."""
        meme_devise = not valeur.devise_comptes or valeur.devise_comptes == valeur.devise
        fin_annee = self._cloture_origine.groupby(self._cloture_origine.index.year).last() \
            if not self._cloture_origine.empty else pd.Series(dtype=float)
        resultat = []
        for c in comptes[-10:]:
            capitalisation = None
            if meme_devise and c.get("nombre_actions") and c["annee"] in fin_annee.index:
                capitalisation = float(fin_annee[c["annee"]]) * c["nombre_actions"]
            if (z := scores.altman(c, capitalisation)) is not None:
                resultat.append(z)
        return resultat

    def _regression(self, reg, fenetre: pd.Series) -> dict:
        # Droite et couloir sur la fenetre, prolonges de quelques annees. L'axe du temps
        # des graphiques avance d'un cran par seance : la projection doit donc aussi
        # avoir un point par jour ouvre, sinon la droite ferait un coude.
        jours = fenetre.index[::5].append(fenetre.index[-1:])
        futur = pd.bdate_range(reg.fin + pd.Timedelta(days=1), periods=PROJECTION_ANS * 261)
        tous = jours.append(futur)
        cle_zone, libelle = zone(reg.position)
        return {
            "debut": reg.debut.strftime("%Y-%m-%d"),
            "fin":   reg.fin.strftime("%Y-%m-%d"),
            "annees": round((reg.fin - reg.debut).days / 365.25, 1),
            "pente": reg.pente,
            "ecart_type": reg.ecart_type,
            "sigma": reg.sigma,
            "r2": reg.r2,
            "position": reg.position,
            "zone": cle_zone,
            "zone_libelle": libelle,
            "retour_droite": reg.retour_droite,
            "valeur_droite": float(reg.droite(fenetre.index[-1:])[0]),
            "dernier": float(fenetre.iloc[-1]),
            "projections": [
                {"ans": n, "valeur": float(reg.droite([reg.fin + pd.DateOffset(years=n)])[0])}
                for n in (1, 3, 5)
            ],
            "repartition": reg.repartition(),
            "theorie": THEORIE,
            "zones": [{"cle": c, "libelle": l} for _, c, l in ZONES],
            "droite": {
                "jours": [d.strftime("%Y-%m-%d") for d in tous],
                **{nom: _liste(reg.droite(tous, k)) for nom, k in
                   (("centre", 0), ("p1", 1), ("p2", 2), ("m1", -1), ("m2", -2))},
            },
        }

    def _stats(self, cloture: pd.Series, mm50, mm200, rsi14) -> dict:
        perte = ind.perte_maximale(cloture)
        precedent = cloture.iloc[-2] if len(cloture) > 1 else None
        debut_annee = cloture[cloture.index < pd.Timestamp(cloture.index[-1].year, 1, 1)]
        return {
            "dernier": float(cloture.iloc[-1]),
            "jour": cloture.index[-1].strftime("%Y-%m-%d"),
            "premier_jour": cloture.index[0].strftime("%Y-%m-%d"),
            "variation_jour": _f(cloture.iloc[-1] / precedent - 1) if precedent else None,
            "perf_ytd": _f(cloture.iloc[-1] / debut_annee.iloc[-1] - 1) if not debut_annee.empty else None,
            "perf_1an": ind.performance(cloture, 365),
            "perf_5ans": ind.performance(cloture, 5 * 365),
            "perf_annuelle": ind.performance_annuelle(cloture),
            "volatilite": ind.volatilite_annuelle(cloture),
            "perte_max": {
                "baisse": perte[0], "sommet": perte[1].strftime("%Y-%m-%d"), "creux": perte[2].strftime("%Y-%m-%d"),
            } if perte else None,
            "rsi": _f(rsi14.iloc[-1]),
            "mm50": _f(mm50.iloc[-1]),
            "mm200": _f(mm200.iloc[-1]),
            "ecart_mm200": _f(cloture.iloc[-1] / mm200.iloc[-1] - 1) if pd.notna(mm200.iloc[-1]) else None,
            "plus_haut_52s": _f(cloture.tail(252).max()),
            "plus_bas_52s": _f(cloture.tail(252).min()),
        }

    # ── Fiches resumees (synthese, screener, comparaison) ─────────────
    def synthese(self) -> list[dict]:
        return [self.fiche_resumee(v) for v in self._db.exec(select(Valeur).order_by(Valeur.nom)).all()]

    def fiche_resumee(self, valeur: Valeur) -> dict:
        """Tout ce qui resume une valeur en une ligne ; calculee une fois, puis gardee en cache."""
        if (en_cache := cache.lire(valeur.id)) is not None:
            return en_cache
        ligne = {"valeur": ValeurRead.model_validate(valeur).model_dump(mode="json")}
        _, cours, _, fenetre, reg = self._contexte(valeur.id, True, None)
        if not cours.empty:
            cloture = cours["cloture"]
            mm200 = ind.moyenne_mobile(cloture, 200)
            rsi14 = ind.rsi(cloture)
            ligne |= {
                "dernier": float(cloture.iloc[-1]),
                "jour": cloture.index[-1].strftime("%Y-%m-%d"),
                "variation_jour": _f(cloture.iloc[-1] / cloture.iloc[-2] - 1) if len(cloture) > 1 else None,
                "perf_1an": ind.performance(cloture, 365),
                "perf_5ans": ind.performance(cloture, 5 * 365),
                "volatilite": ind.volatilite_annuelle(cloture),
                "rsi": _f(rsi14.iloc[-1]),
                "ecart_mm200": _f(cloture.iloc[-1] / mm200.iloc[-1] - 1) if pd.notna(mm200.iloc[-1]) else None,
                "qualite": qualite.controler(cours)["statut"],
            }
        fondamentaux = self._fondamentaux(valeur.id, self._cloture_origine) if not cours.empty else []
        if reg is not None:
            cle_zone, libelle = zone(reg.position)
            verifs = [
                fiabilite.historique(reg),
                fiabilite.per(reg, self._cloture_origine, fondamentaux),
                fiabilite.rupture(reg, fenetre, valeur.rupture),
            ]
            ligne |= {
                "pente": reg.pente, "ecart_type": reg.ecart_type, "position": reg.position,
                "zone": cle_zone, "zone_libelle": libelle, "retour_droite": reg.retour_droite,
                "annees": round((reg.fin - reg.debut).days / 365.25, 1), "r2": reg.r2,
                "fiabilite": fiabilite.verdict(verifs)["statut"],
            }
        comptes = self._comptes(valeur, fondamentaux) if fondamentaux else None
        if comptes:
            s = comptes["synthese"]
            ligne |= {
                "note": comptes["note"]["note"],
                "roic": s.get("roic_moyen_5"), "roe": s.get("roe_moyen_5"),
                "croissance_bpa_10": s.get("croissance_bpa_10") or s.get("croissance_bpa_5"),
                "croissance_ca_10": s.get("croissance_ca_10") or s.get("croissance_ca_5"),
                "dette_nette_ebitda": s.get("dette_nette_ebitda"),
                "marge_operationnelle": s.get("marge_operationnelle_moyenne_10"),
                "piotroski": comptes["piotroski"][-1]["score"] if comptes["piotroski"] else None,
            }
            valo_ = self._valorisation(valeur, fondamentaux, comptes)
            if valo_ and "multiples" in valo_:
                actuels, historique = valo_["multiples"].get("actuels", {}), valo_["multiples"].get("historique", {})
                ligne |= {
                    "per": actuels.get("per"), "ve_ebitda": actuels.get("ve_ebitda"),
                    "rendement_fcf": actuels.get("rendement_fcf"), "rendement_dividende": actuels.get("rendement_dividende"),
                    "capitalisation": actuels.get("capitalisation"),
                    "cherte_per": historique.get("per", {}).get("cherte"),
                    "dcf_inverse": valo_["modeles"].get("dcf_inverse"),
                }
        cache.ecrire(valeur.id, ligne)
        return ligne
