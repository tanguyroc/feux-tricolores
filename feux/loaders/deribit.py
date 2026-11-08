"""Deribit — historique du taux de financement du perpétuel BTC (public, sans clé), horaire depuis juin 2019.

Pourquoi Deribit : les API de Binance et Bybit refusent les requêtes depuis les exécuteurs américains
(HTTP 451/403) ; OKX et Bitget ne gardent que ~3 mois d'historique. Deribit publie l'historique complet
par tranches de 31 jours (744 points horaires au plus par appel).

Sortie : taux de financement QUOTIDIEN (somme des trois périodes de 8 h), en fraction (0.0003 = 0,03 %/jour).
Le fichier brut est mis en cache : seules les tranches manquantes sont redemandées.
"""
from __future__ import annotations

import datetime as dt
import json
import time

import pandas as pd

from ..config import RAW_DIR
from ..store import make_series, save
from . import http_get, log

URL = "https://www.deribit.com/api/v2/public/get_funding_rate_history"
START = dt.date(2019, 6, 1)
CACHE = RAW_DIR / "deribit_funding_hourly.json"


def _ms(d: dt.date) -> int:
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _month_ranges(start: dt.date, end: dt.date):
    cur = start.replace(day=1)
    while cur <= end:
        nxt = (cur.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        yield cur, min(nxt, end + dt.timedelta(days=1))
        cur = nxt


def fetch_hourly() -> pd.DataFrame:
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    today = dt.datetime.now(dt.timezone.utc).date()
    for a, b in _month_ranges(START, today):
        key = a.isoformat()
        complete = key in cache and b <= today  # mois entièrement passé et déjà en cache
        if complete and a.month != today.month:
            continue
        j = http_get(URL, params={"instrument_name": "BTC-PERPETUAL", "start_timestamp": _ms(a), "end_timestamp": _ms(b)}).json()
        rows = j.get("result", [])
        cache[key] = [[r["timestamp"], r["interest_8h"]] for r in rows]
        time.sleep(0.25)
    CACHE.write_text(json.dumps(cache))
    recs = [row for rows in cache.values() for row in rows]
    df = pd.DataFrame(recs, columns=["ts", "interest_8h"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.tz_convert(None)
    df = df.drop_duplicates("ts").sort_values("ts").set_index("ts")
    return df


def update() -> dict[str, pd.DataFrame]:
    h = fetch_hourly()
    # taux horaire « interest_8h » = taux 8 h courant ; moyenne journalière × 3 périodes = financement quotidien
    daily = h["interest_8h"].resample("D").mean() * 3.0
    daily = daily.dropna()
    out = {"btc_funding": make_series(daily.index, daily.values)}
    save("btc_funding", out["btc_funding"])
    log.info("Deribit : %d jours de financement, dernier %s = %.4f %%/j", len(daily), daily.index[-1].date(), 100 * daily.iloc[-1])
    return out
