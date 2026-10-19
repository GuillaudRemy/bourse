"""Indicateurs techniques classiques, calcules sur une serie de clotures indexee par date."""
import numpy as np
import pandas as pd

SEANCES_AN = 252


def moyenne_mobile(cloture: pd.Series, n: int) -> pd.Series:
    return cloture.rolling(n, min_periods=n).mean()


def moyenne_exponentielle(cloture: pd.Series, n: int) -> pd.Series:
    return cloture.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(cloture: pd.Series, n: int = 14) -> pd.Series:
    """RSI de Wilder : lissage exponentiel de facteur 1/n des hausses et des baisses."""
    variation = cloture.diff()
    hausses = variation.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    baisses = (-variation.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = hausses / baisses.replace(0, np.nan)
    resultat = 100 - 100 / (1 + rs)
    return resultat.where(baisses != 0, 100.0).where(hausses.notna())


def macd(cloture: pd.Series, rapide: int = 12, lente: int = 26, signal: int = 9) -> pd.DataFrame:
    ligne = moyenne_exponentielle(cloture, rapide) - moyenne_exponentielle(cloture, lente)
    ligne_signal = ligne.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": ligne, "signal": ligne_signal, "histogramme": ligne - ligne_signal})


def bollinger(cloture: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    centre = moyenne_mobile(cloture, n)
    ecart = cloture.rolling(n, min_periods=n).std(ddof=0)
    return pd.DataFrame({"haut": centre + k * ecart, "milieu": centre, "bas": centre - k * ecart})


def volatilite_annuelle(cloture: pd.Series, seances: int = SEANCES_AN) -> float | None:
    rendements = np.log(cloture).diff().dropna().tail(seances)
    if len(rendements) < 20:
        return None
    return float(rendements.std() * np.sqrt(SEANCES_AN))


def perte_maximale(cloture: pd.Series) -> tuple[float, object, object] | None:
    """Pire baisse d'un sommet a un creux : (baisse, date du sommet, date du creux)."""
    if len(cloture) < 2:
        return None
    sommets = cloture.cummax()
    baisses = cloture / sommets - 1
    creux = baisses.idxmin()
    sommet = cloture.loc[:creux].idxmax()
    return float(baisses.min()), sommet, creux


def performance(cloture: pd.Series, jours: int) -> float | None:
    """Performance sur les `jours` calendaires precedant la derniere seance."""
    if cloture.empty:
        return None
    fin = cloture.index[-1]
    debut = cloture.loc[:fin - pd.Timedelta(days=jours)]
    if debut.empty:
        return None
    return float(cloture.iloc[-1] / debut.iloc[-1] - 1)


def performance_annuelle(cloture: pd.Series) -> float | None:
    """Taux de croissance annuel moyen, du premier au dernier cours."""
    if len(cloture) < 2:
        return None
    annees = (cloture.index[-1] - cloture.index[0]).days / 365.25
    if annees <= 0 or cloture.iloc[0] <= 0:
        return None
    return float((cloture.iloc[-1] / cloture.iloc[0]) ** (1 / annees) - 1)


def signaux(cloture: pd.Series, mm50: pd.Series, mm200: pd.Series, rsi14: pd.Series) -> list[dict]:
    """Lecture rapide de la situation technique. Chaque signal a un ton : hausse, baisse ou neutre."""
    resultat = []
    dernier = cloture.iloc[-1]

    if pd.notna(mm200.iloc[-1]):
        au_dessus = dernier > mm200.iloc[-1]
        ecart = dernier / mm200.iloc[-1] - 1
        resultat.append({
            "ton": "hausse" if au_dessus else "baisse",
            "texte": f"Cours {'au-dessus' if au_dessus else 'en dessous'} de la MM200 ({ecart:+.1%})",
        })

    if pd.notna(mm50.iloc[-1]) and pd.notna(mm200.iloc[-1]):
        ecart = (mm50 - mm200).dropna()
        croisements = ecart[np.sign(ecart).diff().fillna(0) != 0]
        if not croisements.empty:
            jour = croisements.index[-1]
            dore = croisements.iloc[-1] > 0
            resultat.append({
                "ton": "hausse" if dore else "baisse",
                "texte": f"{'Croisement doré' if dore else 'Croisement de la mort'} (MM50 / MM200) le {jour:%d/%m/%Y}",
            })

    if pd.notna(rsi14.iloc[-1]):
        valeur = rsi14.iloc[-1]
        if valeur >= 70:
            resultat.append({"ton": "baisse", "texte": f"RSI en surachat ({valeur:.0f})"})
        elif valeur <= 30:
            resultat.append({"ton": "hausse", "texte": f"RSI en survente ({valeur:.0f})"})
        else:
            resultat.append({"ton": "neutre", "texte": f"RSI neutre ({valeur:.0f})"})

    return resultat
