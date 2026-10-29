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


def signaux(cloture: pd.Series, mm50: pd.Series, mm200: pd.Series, rsi14: pd.Series, points: bool = False) -> list[dict]:
    """Lecture rapide de la situation technique. Chaque signal a un ton : hausse, baisse ou neutre.
    `points=True` (taux d'interet) : l'ecart a la MM200 en points, pas en % du taux."""
    resultat = []
    dernier = cloture.iloc[-1]

    if pd.notna(mm200.iloc[-1]):
        au_dessus = dernier > mm200.iloc[-1]
        ecart = f"{dernier - mm200.iloc[-1]:+.2f} pt".replace(".", ",") if points else f"{dernier / mm200.iloc[-1] - 1:+.1%}"
        resultat.append({
            "ton": "hausse" if au_dessus else "baisse",
            "texte": f"{'Taux' if points else 'Cours'} {'au-dessus' if au_dessus else 'en dessous'} de la MM200 ({ecart})",
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


# ── Indicateurs complementaires ───────────────────────────────────────
def stochastique(haut: pd.Series, bas: pd.Series, cloture: pd.Series, n: int = 14, d: int = 3) -> pd.DataFrame:
    """%K : position de la cloture dans la fourchette des n dernieres seances ; %D : sa moyenne."""
    plus_haut, plus_bas = haut.rolling(n, min_periods=n).max(), bas.rolling(n, min_periods=n).min()
    k = 100 * (cloture - plus_bas) / (plus_haut - plus_bas).replace(0, np.nan)
    return pd.DataFrame({"k": k, "d": k.rolling(d, min_periods=d).mean()})


def atr(haut: pd.Series, bas: pd.Series, cloture: pd.Series, n: int = 14) -> pd.Series:
    """Amplitude moyenne reelle (Wilder) : la volatilite en unites de prix."""
    precedente = cloture.shift(1)
    vraie = pd.concat([haut - bas, (haut - precedente).abs(), (bas - precedente).abs()], axis=1).max(axis=1)
    return vraie.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def adx(haut: pd.Series, bas: pd.Series, cloture: pd.Series, n: int = 14) -> pd.DataFrame:
    """Force de la tendance (ADX, au-dessus de 25 : tendance marquee) et directions +DI / -DI."""
    hausse, baisse = haut.diff(), -bas.diff()
    dm_plus = hausse.where((hausse > baisse) & (hausse > 0), 0.0)
    dm_moins = baisse.where((baisse > hausse) & (baisse > 0), 0.0)
    amplitude = atr(haut, bas, cloture, n)
    di_plus = 100 * dm_plus.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / amplitude
    di_moins = 100 * dm_moins.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / amplitude
    dx = 100 * (di_plus - di_moins).abs() / (di_plus + di_moins).replace(0, np.nan)
    lisse = dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return pd.DataFrame({"adx": lisse, "di_plus": di_plus, "di_moins": di_moins})


def ichimoku(haut: pd.Series, bas: pd.Series, cloture: pd.Series, tenkan: int = 9, kijun: int = 26,
             senkou: int = 52) -> pd.DataFrame:
    """Lignes Ichimoku. Le nuage (senkou A et B) est normalement projete de `kijun` periodes vers
    l'avant ; on le renvoie ici aligne sur la date de calcul, le graphique le decale."""
    milieu = lambda n: (haut.rolling(n, min_periods=n).max() + bas.rolling(n, min_periods=n).min()) / 2  # noqa: E731
    t, k = milieu(tenkan), milieu(kijun)
    return pd.DataFrame({"tenkan": t, "kijun": k, "senkou_a": (t + k) / 2, "senkou_b": milieu(senkou)})


def obv(cloture: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume : volume cumule, ajoute les jours de hausse et retranche les jours de baisse."""
    return (np.sign(cloture.diff()).fillna(0) * volume.fillna(0)).cumsum()
