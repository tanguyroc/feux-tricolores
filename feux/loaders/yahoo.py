"""Prix quotidiens (clôtures) via l'API « chart » de Yahoo Finance.

Source non officielle, mais stable depuis des années et la seule gratuite couvrant
^GSPC (1970-), ^NDX (1985-), ^IXIC (1971-), ^990100-USD-STRD (MSCI World, 1972-), ^VIX, BTC-USD.
Les prix ne sont pas révisés : available_date = ref_date.
"""
from __future__ import annotations

import datetime as dt
import time
import urllib.parse

import pandas as pd

from ..store import make_series, save
from . import http_get, log

URL = ("https://query2.finance.yahoo.com/v8/finance/chart/{sym}"
       "?period1=0&period2=9999999999&interval=1d")


def fetch_close(symbol: str) -> pd.Series:
    r = http_get(URL.format(sym=urllib.parse.quote(symbol, safe="")),
                 headers={"User-Agent": "Mozilla/5.0 feux-tricolores/0.1"})
    res = r.json()["chart"]["result"][0]
    ts = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert(None).normalize()
    close = pd.Series(res["indicators"]["quote"][0]["close"], index=ts, dtype="float64")
    close = close.dropna()
    close = close[~close.index.duplicated(keep="last")].sort_index()
    return close


def spliced(primary: str, splice_with: str | None) -> pd.Series:
    """Chaîne `splice_with` AVANT le début de `primary` en raccordant les niveaux."""
    p = fetch_close(primary)
    if not splice_with:
        return p
    time.sleep(0.8)
    s = fetch_close(splice_with)
    s = s[s.index < p.index[0]]
    if s.empty:
        return p
    # raccord : le dernier point de s est rescalé sur le premier point de p
    ratio = p.iloc[0] / s.iloc[-1]
    return pd.concat([s * ratio, p]).sort_index()


def update(assets: dict, extra: dict | None = None) -> dict[str, pd.DataFrame]:
    out = {}
    for key, spec in assets.items():
        close = spliced(spec["ticker"], spec.get("splice"))
        out[f"px_{key}"] = make_series(close.index, close.values)
        time.sleep(0.8)
    for key, sym in (extra or {}).items():
        close = fetch_close(sym)
        out[f"px_{key}"] = make_series(close.index, close.values)
        time.sleep(0.8)
    for k, v in out.items():
        save(k, v)
    log.info("Yahoo : %s", ", ".join(f"{k}:{v['ref_date'].iloc[0].date()}→{v['ref_date'].iloc[-1].date()}" for k, v in out.items()))
    return out
