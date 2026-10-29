"""Seconde source de cours, pour contre-verifier Yahoo sur la periode recente.

- Euronext (Paris, Amsterdam, Bruxelles, Lisbonne, Milan, Oslo, Dublin) : 2 ans de cours officiels par ISIN ;
  la recherche par symbole donne aussi l'ISIN, qui sert ensuite a retrouver les comptes officiels.
- Nasdaq (actions americaines) : 2 ans aussi (l'API refuse au-dela de 5 ans).
Stooq, autrefois pratique, bloque desormais les telechargements automatises : non utilise.

Les deux sources donnent des clotures ajustees des divisions mais pas des dividendes, comme la colonne
« cloture » de Yahoo : on compare donc cloture a cloture.
"""
import io
import re
from datetime import date, timedelta

import pandas as pd

from backend.sources.base import SourceIndisponible
from backend.sources.reseau import ErreurReseau, obtenir

NAVIGATEUR = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
# Suffixe Yahoo -> marche Euronext (code MIC)
EURONEXT = {"PA": "XPAR", "AS": "XAMS", "BR": "XBRU", "LS": "XLIS", "MI": "XMIL", "OL": "XOSL", "IR": "XDUB"}
PLACES_US = {"NMS", "NYQ", "NGM", "NCM", "ASE", "PCX", "BTS", "NasdaqGS", "NYSE", "NasdaqGM", "NasdaqCM"}
ECART = 0.01                    # au-dela, deux clotures du meme jour sont jugees differentes


def couvre(symbole: str, place: str | None, type_: str) -> bool:
    if type_ not in ("action", "etf", "obligation"):
        return False
    suffixe = symbole.rsplit(".", 1)[1] if "." in symbole else ""
    return suffixe in EURONEXT or (not suffixe and (place or "") in PLACES_US)


def isin_euronext(symbole: str) -> tuple[str, str] | None:
    """(ISIN, MIC) d'un symbole Yahoo d'Euronext (« MC.PA » -> FR0000121014, XPAR), ou None."""
    code, suffixe = symbole.rsplit(".", 1)
    mic = EURONEXT[suffixe]
    try:
        resultats = obtenir("https://live.euronext.com/en/instrumentSearch/searchJSON", params={"q": code},
                            entetes=NAVIGATEUR).json()
    except (ErreurReseau, ValueError) as e:
        raise SourceIndisponible(f"Euronext : recherche de {symbole} impossible ({e})") from e
    for r in resultats:
        trouve = re.search(r"class='symbol'>([^<]+)<", r.get("label", ""))
        lien = r.get("link", "")
        meme_titre = r.get("mic") == mic and trouve and trouve.group(1).upper() == code.upper()
        if meme_titre and ("/equities/" in lien or "/etf" in lien):
            return r["isin"], mic
    return None


def euronext(isin: str, mic: str) -> pd.Series:
    """Clotures des 2 dernieres annees (le maximum publie), indexees par date."""
    fin = date.today()
    url = f"https://live.euronext.com/en/ajax/AwlHistoricalPrice/getFullDownloadAjax/{isin}-{mic}"
    params = {"format": "csv", "decimal_separator": ".", "date_form": "d/m/Y", "op": "", "adjusted": "Y", "base100": "",
              "startdate": (fin - timedelta(days=800)).isoformat(), "enddate": fin.isoformat()}
    try:
        texte = obtenir(url, params=params, entetes=NAVIGATEUR).content.decode("utf-8-sig")
    except ErreurReseau as e:
        raise SourceIndisponible(f"Euronext : cours de {isin} indisponibles ({e})") from e
    lignes = texte.splitlines()
    debut = next((i for i, ligne in enumerate(lignes) if ligne.startswith("Date;")), None)
    if debut is None:
        return pd.Series(dtype=float)
    df = pd.read_csv(io.StringIO("\n".join(lignes[debut:])), sep=";")
    serie = pd.Series(pd.to_numeric(df["Close"], errors="coerce").to_numpy(),
                      index=pd.to_datetime(df["Date"], format="%d/%m/%Y"))
    return serie.dropna().sort_index()


def nasdaq(symbole: str) -> pd.Series:
    """Clotures des 2 dernieres annees d'une action americaine."""
    fin = date.today()
    try:
        donnees = obtenir(f"https://api.nasdaq.com/api/quote/{symbole}/historical",
                          params={"assetclass": "stocks", "fromdate": (fin - timedelta(days=800)).isoformat(),
                                  "todate": fin.isoformat(), "limit": 9999},
                          entetes={**NAVIGATEUR, "Accept": "application/json"}).json()
    except (ErreurReseau, ValueError) as e:
        raise SourceIndisponible(f"Nasdaq : cours de {symbole} indisponibles ({e})") from e
    lignes = (((donnees or {}).get("data") or {}).get("tradesTable") or {}).get("rows") or []
    serie = pd.Series({pd.to_datetime(r["date"], format="%m/%d/%Y"): float(r["close"].replace("$", "").replace(",", ""))
                       for r in lignes if r.get("close")}, dtype=float)
    return serie.sort_index()


def comparer(yahoo: pd.Series, autre: pd.Series, source: str) -> dict:
    """Jours communs, jours en desaccord (> 1 %), plus grand ecart."""
    communs = yahoo.index.intersection(autre.index)
    if len(communs) == 0:
        return {"source": source, "jours": 0, "desaccords": 0, "statut": "inconnu", "le": date.today().isoformat()}
    ecart = (yahoo[communs] / autre[communs] - 1)
    pire = ecart.abs().idxmax()
    desaccords = int((ecart.abs() > ECART).sum())
    return {
        "source": source, "jours": int(len(communs)), "desaccords": desaccords,
        "ecart_max": float(ecart[pire]), "jour_ecart_max": pire.strftime("%Y-%m-%d"),
        "debut": communs.min().strftime("%Y-%m-%d"), "le": date.today().isoformat(),
        "statut": "ok" if desaccords == 0 else "attention" if desaccords <= 3 else "alerte",
    }
