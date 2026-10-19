"""Assemble l'analyse complete d'une valeur : series pour les graphiques,
droite de regression, indicateurs techniques, fiabilite et fondamentaux."""
import math
from datetime import date
import numpy as np
import pandas as pd
from fastapi import HTTPException
from sqlmodel import Session, select
from backend.analyse import indicateurs as ind
from backend.analyse import fiabilite
from backend.analyse.regression import ajuster, zone, THEORIE, ZONES
from backend.core.config import config
from backend.db.schema import Valeur, Fondamental
from backend.models.valeur import ValeurRead
from backend.services.stockage import charger_cours

PROJECTION_ANS = 3


def _liste(serie, decimales: int = 4) -> list:
    """Serie -> liste JSON (NaN -> null)."""
    return [None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), decimales)
            for v in serie]


def _f(v):
    return None if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else float(v)


def debut_par_defaut(valeur: Valeur) -> date:
    annee = config.DEBUT_INDICES if valeur.type == "indice" else config.DEBUT_ACTIONS
    return date(annee, 1, 1)


class AnalyseService:
    def __init__(self, session: Session):
        self._db = session

    def _contexte(self, valeur_id: int, dividendes: bool, debut: date | None):
        valeur = self._db.get(Valeur, valeur_id)
        if not valeur:
            raise HTTPException(404, "Valeur introuvable.")
        cours = charger_cours(self._db, valeur_id)
        if cours.empty:
            return valeur, cours, None, None, None

        # Base de la droite : rendement total si disponible, sinon cloture.
        base_ajustee = bool(dividendes and cours["ajuste"].notna().mean() > 0.9)
        base = (cours["ajuste"] if base_ajustee else cours["cloture"]).dropna()

        debut = debut or valeur.debut_regression or debut_par_defaut(valeur)
        fenetre = base[base.index >= pd.Timestamp(debut)]
        if len(fenetre) < 250:          # trop court depuis le debut choisi : tout l'historique
            fenetre = base
        return valeur, cours, base_ajustee, fenetre, ajuster(fenetre)

    def _fondamentaux(self, valeur_id: int, cloture: pd.Series) -> list[dict]:
        lignes = self._db.exec(
            select(Fondamental).where(Fondamental.valeur_id == valeur_id).order_by(Fondamental.annee)
        ).all()
        fond = [l.model_dump(include={"annee", "bpa", "benefice_net", "chiffre_affaires", "dividende", "source"})
                for l in lignes]
        pers = fiabilite.per_annuels(cloture, fond) if not cloture.empty else {}
        for f in fond:
            f["per"] = pers.get(f["annee"])
        return fond

    # ── Fiche complete ────────────────────────────────────────────────
    def analyse(self, valeur_id: int, dividendes: bool = True, debut: date | None = None) -> dict:
        valeur, cours, base_ajustee, fenetre, reg = self._contexte(valeur_id, dividendes, debut)
        resultat = {
            "valeur": ValeurRead.model_validate(valeur).model_dump(mode="json"),
            "debut_defaut": debut_par_defaut(valeur).isoformat(),
            "vide": cours.empty,
        }
        if cours.empty:
            return resultat

        cloture = cours["cloture"]
        mm20, mm50, mm200 = (ind.moyenne_mobile(cloture, n) for n in (20, 50, 200))
        rsi14 = ind.rsi(cloture)
        macd = ind.macd(cloture)
        boll = ind.bollinger(cloture)
        fondamentaux = self._fondamentaux(valeur_id, cloture)

        resultat |= {
            "base_ajustee": base_ajustee,
            "series": {
                "jours":     [d.strftime("%Y-%m-%d") for d in cours.index],
                "ouverture": _liste(cours["ouverture"]),
                "haut":      _liste(cours["haut"]),
                "bas":       _liste(cours["bas"]),
                "cloture":   _liste(cloture),
                "ajuste":    _liste(cours["ajuste"]),
                "volume":    _liste(cours["volume"], 0),
            },
            "indicateurs": {
                "mm20": _liste(mm20), "mm50": _liste(mm50), "mm200": _liste(mm200),
                "rsi": _liste(rsi14, 2),
                "macd": _liste(macd["macd"]), "macd_signal": _liste(macd["signal"]),
                "macd_histogramme": _liste(macd["histogramme"]),
                "bollinger_haut": _liste(boll["haut"]), "bollinger_bas": _liste(boll["bas"]),
            },
            "stats": self._stats(cloture, mm50, mm200, rsi14),
            "signaux": ind.signaux(cloture, mm50, mm200, rsi14),
            "fondamentaux": fondamentaux,
        }

        if reg is None:
            resultat["regression"] = None
            return resultat

        resultat["regression"] = self._regression(reg, fenetre)
        verifs = [
            fiabilite.historique(reg),
            fiabilite.per(reg, cloture, fondamentaux),
            fiabilite.rupture(reg, fenetre, valeur.rupture),
        ]
        resultat["fiabilite"] = {"verifications": verifs, "verdict": fiabilite.verdict(verifs)}
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

    # ── Tableau de synthese ───────────────────────────────────────────
    def synthese(self) -> list[dict]:
        lignes = []
        for valeur in self._db.exec(select(Valeur).order_by(Valeur.nom)).all():
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
                    "rsi": _f(rsi14.iloc[-1]),
                    "ecart_mm200": _f(cloture.iloc[-1] / mm200.iloc[-1] - 1) if pd.notna(mm200.iloc[-1]) else None,
                }
            if reg is not None:
                cle_zone, libelle = zone(reg.position)
                verifs = [
                    fiabilite.historique(reg),
                    fiabilite.per(reg, cours["cloture"], self._fondamentaux(valeur.id, cours["cloture"])),
                    fiabilite.rupture(reg, fenetre, valeur.rupture),
                ]
                ligne |= {
                    "pente": reg.pente, "ecart_type": reg.ecart_type, "position": reg.position,
                    "zone": cle_zone, "zone_libelle": libelle, "retour_droite": reg.retour_droite,
                    "annees": round((reg.fin - reg.debut).days / 365.25, 1),
                    "fiabilite": fiabilite.verdict(verifs)["statut"],
                }
            lignes.append(ligne)
        return lignes
