"""FRED (fredgraph.csv, sans clé). Séries quotidiennes/mensuelles/trimestrielles.

Limite connue : fredgraph renvoie le dernier millésime (révisions incluses). Pour les séries
révisées (Z.1), la disponibilité est approximée par un décalage de publication ; les vintages
ALFRED pourront remplacer cette approximation plus tard.
"""
from __future__ import annotations

import io

import pandas as pd

from ..config import rules
from ..store import make_series, save
from . import http_get, log

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

# BAA10Y = rendement Baa (Moody's) − Treasury 10 ans, quotidien depuis 1986.
# L'OAS haut rendement ICE (BAMLH0A0HYM2) n'est téléchargeable que sur 3 ans (licence) : inutilisable en backtest.
DAILY = {"VIXCLS": "vix", "BAA10Y": "credit_spread", "DGS10": "dgs10"}
MONTHLY = {"TB3MS": "tbill3m"}
# AIAE (Philosophical Economics) : actions / (actions + passifs des emprunteurs réels)
AIAE_NUM = ["NCBEILQ027S", "FBCELLQ027S"]          # millions de dollars (FRED, Z.1)
AIAE_DEN = ["FGSDODNS", "CMDEBT", "BCNSDODNS", "DODFFSWCMI", "SLGSDODNS"]  # millions de dollars également (unités harmonisées par FRED)


def fetch(sid: str) -> pd.Series:
    txt = http_get(URL.format(sid=sid)).text
    df = pd.read_csv(io.StringIO(txt))
    df.columns = ["date", "value"]
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df.dropna().set_index("date")["value"].sort_index()


def update() -> dict[str, pd.DataFrame]:
    out = {}
    for sid, name in DAILY.items():
        s = fetch(sid)
        out[name] = make_series(s.index, s.values)
    for sid, name in MONTHLY.items():
        s = fetch(sid)
        out[name] = make_series(s.index + pd.offsets.MonthEnd(0), s.values, lag=pd.Timedelta(days=7))
    # AIAE trimestriel
    num = sum(fetch(sid) for sid in AIAE_NUM)
    den_parts = [fetch(sid) for sid in AIAE_DEN]
    den = sum(den_parts)
    aiae = (num / (num + den)).dropna()
    if not (0.15 < aiae.iloc[-1] < 0.80):
        raise ValueError(f"AIAE hors plage plausible ({aiae.iloc[-1]:.4f}) : unités FRED probablement changées")
    lag_days = int(rules()["lags"]["aiae_days_after_quarter_end"])
    qend = aiae.index + pd.offsets.QuarterEnd(0)
    out["aiae"] = make_series(qend, aiae.values, lag=pd.Timedelta(days=lag_days))
    for k, v in out.items():
        save(k, v)
    log.info("FRED : %s", ", ".join(f"{k}={len(v)}" for k, v in out.items()))
    return out
