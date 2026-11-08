"""Coin Metrics Community API (gratuite, CC BY-NC 4.0) : prix et MVRV quotidiens depuis 2010.

Note : CapRealUSD n'est pas disponible dans l'offre communautaire (403) ; MVRV suffit."""
from __future__ import annotations

import time

import pandas as pd

from ..store import make_series, save
from . import http_get, log

URL = ("https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
       "?assets=btc&metrics=PriceUSD,CapMVRVCur&frequency=1d&page_size=10000"
       "&start_time=2010-07-18&paging_from=start")


def fetch() -> pd.DataFrame:
    rows, url = [], URL
    while url:
        j = http_get(url).json()
        rows.extend(j.get("data", []))
        url = j.get("next_page_url")
        if url:
            time.sleep(0.7)  # limite : 10 requêtes / 6 s
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_convert(None).dt.normalize()
    for c in ["PriceUSD", "CapMVRVCur"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.set_index("time").sort_index()


def update() -> dict[str, pd.DataFrame]:
    df = fetch()
    out = {
        "btc_price": make_series(df.index, df["PriceUSD"]),
        "btc_mvrv": make_series(df.index, df["CapMVRVCur"]),
    }
    for k, v in out.items():
        save(k, v)
    log.info("Coin Metrics : %d jours, dernier %s, prix %.0f, MVRV %.2f", len(df), df.index[-1].date(),
             df["PriceUSD"].dropna().iloc[-1], df["CapMVRVCur"].dropna().iloc[-1])
    return out
