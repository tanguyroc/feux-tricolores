"""Univers « Top 100 mondial » : les 100 premières pondérations du MSCI ACWI (capitalisation flottante),
lues chaque jour dans le fichier de positions public de l'ETF SPDR MSCI ACWI UCITS (State Street).

Correspondances :
- ISIN -> symbole Yahoo du marché domestique (recherche Yahoo par ISIN, mise en cache) ;
- nom -> CIK SEC (fichier company_tickers_exchange.json, nécessite SEC_USER_AGENT) pour les sociétés qui déposent
  un 10-K ou un 20-F ; sinon la société est suivie « en prix seul » ;
- éligibilité PEA approximée par le pays du siège (UE/EEE) : à vérifier titre par titre chez le courtier.
"""
from __future__ import annotations

import json
import os
import re
import time

import pandas as pd

from .config import DATA_DIR, RAW_DIR
from .loaders import http_get, log

SSGA_URL = "https://www.ssga.com/library-content/products/fund-data/etfs/emea/holdings-daily-emea-en-spyy-gy.xlsx"
YAHOO_SEARCH = "https://query2.finance.yahoo.com/v1/finance/search"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers_exchange.json"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) feux-tricolores/0.1"}
UNIVERSE_CSV = DATA_DIR / "universe.csv"
MAP_CACHE = RAW_DIR / "isin_symbols.json"

EEA = {"Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czech Republic", "Czechia", "Denmark", "Estonia", "Finland", "France",
       "Germany", "Greece", "Hungary", "Iceland", "Ireland", "Italy", "Latvia", "Liechtenstein", "Lithuania", "Luxembourg", "Malta",
       "Netherlands", "Norway", "Poland", "Portugal", "Romania", "Slovakia", "Slovenia", "Spain", "Sweden"}

# Noms Yahoo introuvables par ISIN : recherche par nom, ou symbole imposé
NAME_FALLBACK = {"SA2030P0K6M7": "Saudi Arabian Oil"}
SYMBOL_OVERRIDES = {"US02079K3059": {"symbol": "GOOGL", "exchange": "NMS", "us_symbol": "GOOGL"}}
# Correspondances SEC manuelles (noms trop différents entre MSCI et EDGAR)
SEC_OVERRIDES = {"Alphabet Inc. Class A": 1652044, "Alphabet Inc. Class C": 1652044, "Berkshire Hathaway Inc. Class B": 1067983,
                 "Meta Platforms Inc Class A": 1326801}


def download_holdings() -> pd.DataFrame:
    path = RAW_DIR / "spyy_holdings.xlsx"
    path.write_bytes(http_get(SSGA_URL, headers=UA).content)
    raw = pd.read_excel(path, header=None)
    hdr = raw.index[raw.iloc[:, 0].astype(str).str.strip() == "ISIN"][0]
    as_of = str(raw.iloc[3, 1])
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [str(c).strip() for c in raw.iloc[hdr]]
    df = df.rename(columns={"ISIN": "isin", "Security Name": "name", "Currency": "currency", "Percent of Fund": "weight",
                            "Trade Country Name": "country", "Sector Classification": "sector", "Industry Classification": "industry",
                            "Local Price": "local_price", "Base Market Value": "market_value_usd"})
    df = df[df["isin"].astype(str).str.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d")]
    df = df[df["sector"].notna() & (df["sector"].astype(str) != "-")]
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
    df = df.dropna(subset=["weight"]).sort_values("weight", ascending=False)
    df.attrs["as_of"] = as_of
    return df[["isin", "name", "currency", "weight", "country", "sector", "industry", "local_price", "market_value_usd"]].reset_index(drop=True)


def _yahoo_lookup(isin: str, name: str) -> dict:
    if isin in SYMBOL_OVERRIDES:
        return dict(SYMBOL_OVERRIDES[isin])
    for q in ([isin] + ([NAME_FALLBACK[isin]] if isin in NAME_FALLBACK else []) + [name]):
        try:
            j = http_get(YAHOO_SEARCH, params={"q": q, "quotesCount": 10, "newsCount": 0, "listsCount": 0}, headers=UA).json()
        except Exception as exc:  # noqa: BLE001
            log.warning("Yahoo search %s : %s", q, exc)
            continue
        quotes = [x for x in j.get("quotes", []) if x.get("quoteType") == "EQUITY"]
        if quotes:
            home = quotes[0]
            us = next((x for x in quotes if x.get("exchange") in ("NMS", "NYQ", "NGM", "NCM")), None)
            return {"symbol": home["symbol"], "exchange": home.get("exchange"), "us_symbol": us["symbol"] if us else None}
        time.sleep(0.3)
    return {"symbol": None, "exchange": None, "us_symbol": None}


def map_symbols(df: pd.DataFrame) -> pd.DataFrame:
    cache = json.loads(MAP_CACHE.read_text()) if MAP_CACHE.exists() else {}
    for isin, name in zip(df["isin"], df["name"]):
        if isin not in cache or not cache[isin].get("symbol"):
            cache[isin] = _yahoo_lookup(isin, name)
            time.sleep(0.5)
    MAP_CACHE.write_text(json.dumps(cache, indent=0))
    df["symbol"] = df["isin"].map(lambda i: cache.get(i, {}).get("symbol"))
    df["us_symbol"] = df["isin"].map(lambda i: cache.get(i, {}).get("us_symbol"))
    return df


def _norm(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", str(name).lower())
    for w in ("incorporated", "inc", "corporation", "corp", "company", "co", "ltd", "limited", "plc", "nv", "n v", "sa", "se", "ag", "kgaa",
              "holdings", "holding", "group", "class a", "class b", "class c", "the", "ord", "adr", "common stock", "registered", "shares", "reg"):
        n = re.sub(rf"\b{w}\b", " ", n)
    return " ".join(n.split())


def map_sec(df: pd.DataFrame) -> pd.DataFrame:
    """CIK par nom normalisé (et ticker américain quand Yahoo en donne un). Sans SEC_USER_AGENT : colonne vide."""
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    df["cik"] = pd.NA
    if "@" not in ua:
        log.warning("SEC_USER_AGENT absent : pas de correspondance CIK (sociétés suivies en prix seul)")
        return df
    j = http_get(SEC_TICKERS, headers={"User-Agent": ua}).json()
    fields = j["fields"]
    rows = [dict(zip(fields, r)) for r in j["data"]]
    by_ticker = {r["ticker"].upper().replace("-", "."): r["cik"] for r in rows if r.get("ticker")}
    by_name = {}
    for r in rows:
        by_name.setdefault(_norm(r["name"]), r["cik"])
    ciks = []
    for name, sym, us in zip(df["name"], df["symbol"], df["us_symbol"]):
        sym = sym if isinstance(sym, str) else None
        us = us if isinstance(us, str) else None
        cik = SEC_OVERRIDES.get(name)
        if cik is None and us:
            cik = by_ticker.get(us.upper().replace("-", "."))
        if cik is None and sym and "." not in sym:
            cik = by_ticker.get(sym.upper().replace("-", "."))
        if cik is None:
            cik = by_name.get(_norm(name))
        ciks.append(cik)
    df["cik"] = pd.array(ciks, dtype="Int64")
    log.info("SEC : %d sociétés sur %d avec un CIK", df["cik"].notna().sum(), len(df))
    return df


def _company_key(name: str) -> str:
    return re.sub(r"\s+class\s+[abc]\b.*$", "", _norm(name))


def build(top: int = 100) -> pd.DataFrame:
    h = download_holdings()
    as_of = h.attrs["as_of"]
    # une société = une ligne (Alphabet A/C, Berkshire...) : on garde la classe la plus pondérée et on complète à `top`
    h["company"] = h["name"].map(_company_key)
    df = h.drop_duplicates("company", keep="first").head(top).copy()
    df = map_symbols(df)
    df = map_sec(df)
    df["pea_eligible_approx"] = df["country"].isin(EEA)
    df["rank"] = range(1, len(df) + 1)
    df["as_of"] = as_of
    df.to_csv(UNIVERSE_CSV, index=False)
    log.info("Univers : %d sociétés (positions SPDR MSCI ACWI au %s) ; %d symboles Yahoo, %d CIK, %d éligibles PEA (approx.)",
             len(df), as_of, df["symbol"].notna().sum(), df["cik"].notna().sum(), int(df["pea_eligible_approx"].sum()))
    return df


def load() -> pd.DataFrame:
    if not UNIVERSE_CSV.exists():
        raise FileNotFoundError("data/universe.csv absent : lancer `python -m feux universe`")
    return pd.read_csv(UNIVERSE_CSV, dtype={"cik": "Int64"})
