"""Données de Robert Shiller (ie_data.xls) : prix, dividendes, bénéfices, CPI, GS10, CAPE, ECY.

Le lien du fichier change de version ; on le relit sur la page d'accueil à chaque fois.
"""
from __future__ import annotations

import re

import pandas as pd

from ..config import RAW_DIR, rules
from ..store import make_series, save
from . import http_get, log

HOME = "https://shillerdata.com/"
FALLBACK = ("https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/"
            "downloads/1449043e-a1ed-4e2e-8e9c-7b9a2a064493/ie_data.xls")

COLS = {0: "date", 1: "P", 2: "D", 3: "E", 4: "CPI", 6: "GS10", 12: "CAPE_shiller", 16: "ECY_shiller"}


def _find_url() -> str:
    try:
        html = http_get(HOME, headers={"User-Agent": "Mozilla/5.0 feux-tricolores/0.1"}).text
        m = re.search(r'href="(//img1\.wsimg\.com/[^"]*ie_data\.xls[^"]*)"', html)
        if m:
            return "https:" + m.group(1)
    except Exception as exc:  # noqa: BLE001
        log.warning("Page Shiller illisible (%s), URL de secours", exc)
    return FALLBACK


def download() -> pd.DataFrame:
    url = _find_url()
    path = RAW_DIR / "ie_data.xls"
    path.write_bytes(http_get(url, headers={"User-Agent": "Mozilla/5.0 feux-tricolores/0.1"}).content)
    return parse(path)


def parse(path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="Data", header=None)
    df = raw.iloc[8:, list(COLS)].copy()
    df.columns = list(COLS.values())
    df = df[pd.to_numeric(df["date"], errors="coerce").notna()].copy()
    # 1871.01 -> 1871-01 ; attention 2026.1 == octobre (format décimal tronqué)
    year = df["date"].astype(float).astype(int)
    month = ((df["date"].astype(float) - year) * 100).round().astype(int)
    month = month.where(month > 0, 10)  # ".1" lu comme ".10"
    df["ref_date"] = pd.to_datetime(dict(year=year, month=month, day=1)) + pd.offsets.MonthEnd(0)
    for c in ["P", "D", "E", "CPI", "GS10", "CAPE_shiller", "ECY_shiller"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.set_index("ref_date").drop(columns="date").sort_index()


def build_series(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Séries mensuelles point-in-time.

    - P, CPI, GS10 : connus en fin de mois (disponibilité = fin de mois).
    - E (bénéfices) : disponibilité décalée de `shiller_earnings_months` mois.
    - CAPE_pit : calculé ici avec les bénéfices décalés (voir indicators.cape_pit).
    """
    lag_m = int(rules()["lags"]["shiller_earnings_months"])
    out = {
        "shiller_P": make_series(df.index, df["P"]),
        "shiller_D": make_series(df.index, df["D"]),
        "shiller_CPI": make_series(df.index, df["CPI"], lag=pd.Timedelta(days=15)),
        "shiller_GS10": make_series(df.index, df["GS10"]),
        "shiller_E": make_series(df.index, df["E"], lag=pd.DateOffset(months=lag_m)),
        "shiller_CAPE": make_series(df.index, df["CAPE_shiller"]),
        "shiller_ECY": make_series(df.index, df["ECY_shiller"]),
    }
    return out


def update() -> dict[str, pd.DataFrame]:
    df = download()
    series = build_series(df)
    for k, v in series.items():
        save(k, v)
    log.info("Shiller : %d mois, dernier %s, CAPE %.2f", len(df), df.index[-1].date(), df["CAPE_shiller"].dropna().iloc[-1])
    return series
