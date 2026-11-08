"""Crypto Fear & Greed Index (alternative.me), quotidien depuis février 2018."""
from __future__ import annotations

import pandas as pd

from ..store import make_series, save
from . import http_get, log

URL = "https://api.alternative.me/fng/?limit=0&format=json"


def update() -> dict[str, pd.DataFrame]:
    j = http_get(URL).json()
    df = pd.DataFrame(j["data"])
    df["ts"] = pd.to_datetime(pd.to_numeric(df["timestamp"]), unit="s").dt.normalize()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.sort_values("ts")
    out = {"btc_fng": make_series(df["ts"], df["value"])}
    save("btc_fng", out["btc_fng"])
    log.info("Fear & Greed : %d jours, dernier %s = %.0f", len(df), df["ts"].iloc[-1].date(), df["value"].iloc[-1])
    return out
