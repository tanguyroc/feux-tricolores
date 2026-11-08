"""FINRA — dette sur marge (debit balances in customers' securities margin accounts), mensuel depuis 1997."""
from __future__ import annotations

import re

import pandas as pd

from ..config import RAW_DIR, rules
from ..store import make_series, save
from . import http_get, log

PAGE = "https://www.finra.org/rules-guidance/key-topics/margin-accounts/margin-statistics"
FALLBACK = "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"
UA = {"User-Agent": "Mozilla/5.0 feux-tricolores/0.1"}


def _find_url() -> str:
    try:
        html = http_get(PAGE, headers=UA).text
        m = re.search(r'href="(/sites/default/files/[^"]*margin-statistics[^"]*\.xlsx)"', html)
        if m:
            return "https://www.finra.org" + m.group(1)
    except Exception as exc:  # noqa: BLE001
        log.warning("Page FINRA illisible (%s), URL de secours", exc)
    return FALLBACK


def parse(path) -> pd.Series:
    raw = pd.read_excel(path, header=None)
    raw = raw.iloc[1:, :2]
    raw.columns = ["ym", "debit"]
    raw = raw[raw["ym"].astype(str).str.match(r"^\d{4}-\d{2}$")]
    idx = pd.to_datetime(raw["ym"].astype(str) + "-01") + pd.offsets.MonthEnd(0)
    s = pd.Series(pd.to_numeric(raw["debit"], errors="coerce").to_numpy(), index=idx).dropna().sort_index()
    return s  # millions de dollars


def update() -> dict[str, pd.DataFrame]:
    path = RAW_DIR / "margin-statistics.xlsx"
    path.write_bytes(http_get(_find_url(), headers=UA).content)
    s = parse(path)
    lag = pd.Timedelta(days=int(rules()["lags"]["margin_debt_days_after_month_end"]))
    out = {"margin_debt": make_series(s.index, s.values, lag=lag)}
    save("margin_debt", out["margin_debt"])
    log.info("FINRA : %d mois, dernier %s = %.0f M$", len(s), s.index[-1].date(), s.iloc[-1])
    return out
