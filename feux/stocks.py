"""Module actions individuelles : valorisation point-in-time (EDGAR), DCF inversé, filtre qualité,
extension de prix, couleur. Les sociétés « proxys crypto » suivent le feu Bitcoin."""
from __future__ import annotations

import json
import logging
import pathlib

import numpy as np
import pandas as pd
import yaml

from . import indicators as ind
from . import store
from .config import DATA_DIR, DOCS_DIR, ROOT, rules
from .loaders import edgar, yahoo
from .signals import SIGNALS_DIR, confirmed_color, load_signals

log = logging.getLogger("feux.stocks")
STOCKS_PATH = ROOT / "stocks.yaml"
TD = 252


def watchlist() -> dict:
    with open(STOCKS_PATH, encoding="utf-8") as fh:
        wl = yaml.safe_load(fh)["stocks"]
    return {str(k): v for k, v in wl.items()}   # une clé numérique (9984) doit rester une chaîne


def _asof(df: pd.DataFrame, cal: pd.DatetimeIndex) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(np.nan, index=cal)
    s = store.make_series(df["end"], df["val"], available_dates=df["filed"])
    # plusieurs périodes peuvent être déposées le même jour : garder la plus récente
    s = s.sort_values(["available_date", "ref_date"]).drop_duplicates("available_date", keep="last")
    return store.as_of(s, cal)


def implied_growth(ev: float, fcf: float, wacc: float, g_term: float, years: int) -> float:
    """Croissance annuelle du FCF sur `years` ans qui égalise la valeur actuelle des flux à l'EV (bissection)."""
    if not (fcf > 0 and ev > 0):
        return np.nan

    def pv(g):
        flows = fcf * (1 + g) ** np.arange(1, years + 1)
        disc = (1 + wacc) ** np.arange(1, years + 1)
        terminal = flows[-1] * (1 + g_term) / (wacc - g_term) / disc[-1]
        return float((flows / disc).sum() + terminal)

    lo, hi = -0.5, 1.5
    if pv(lo) > ev:
        return lo
    if pv(hi) < ev:
        return hi
    for _ in range(60):
        mid = (lo + hi) / 2
        if pv(mid) < ev:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def analyse_operating(key: str, spec: dict) -> pd.DataFrame:
    r = rules()["stocks"]
    px = yahoo.fetch_close(spec["ticker"])
    cal = px.index
    f = edgar.fundamentals(int(spec["cik"]))
    df = pd.DataFrame({"price": px})
    for k in ("revenue", "ebit", "net_income", "cfo", "capex", "da", "cash", "st_investments", "debt_lt", "debt_st", "equity", "shares"):
        df[k] = _asof(f.get(k), cal)
    df["fcf"] = df["cfo"] - df["capex"].fillna(0.0)
    df["debt"] = df["debt_lt"].fillna(0.0) + df["debt_st"].fillna(0.0)
    df["liquidity"] = df["cash"].fillna(0.0) + df["st_investments"].fillna(0.0)
    df["mcap"] = df["price"] * df["shares"]
    df["ev"] = df["mcap"] + df["debt"] - df["liquidity"]
    df["ev_ebit"] = (df["ev"] / df["ebit"]).where(df["ebit"] > 0)
    df["p_fcf"] = (df["mcap"] / df["fcf"]).where(df["fcf"] > 0)
    w, mn = TD * r["valuation"]["pct_years"], TD * r["valuation"]["pct_min_years"]
    df["ev_ebit_pct"] = ind.rolling_pct(df["ev_ebit"], w, mn)
    df["p_fcf_pct"] = ind.rolling_pct(df["p_fcf"], w, mn)
    df["V"] = df[["ev_ebit_pct", "p_fcf_pct"]].median(axis=1, skipna=True)
    # qualité
    q = r["quality"]
    invested = df["equity"] + df["debt"] - df["liquidity"]
    df["roic"] = (df["ebit"] * (1 - q["tax_rate"]) / invested).where(invested > 0)
    df["fcf_ni"] = (df["fcf"] / df["net_income"]).where(df["net_income"] > 0)
    ebitda = df["ebit"] + df["da"].fillna(0.0)
    df["nd_ebitda"] = ((df["debt"] - df["liquidity"]) / ebitda).where(ebitda > 0)
    df["quality_ok"] = (df["roic"] >= q["roic_min"]) & (df["fcf_ni"] >= q["fcf_to_net_income_min"]) & (df["nd_ebitda"] <= q["net_debt_to_ebitda_max"])
    # extension
    g = r["extension"]["gsy"]
    df["gap_ma200"] = ind.gap_to_ma(px, 200)
    df["gap_ma200_pct"] = ind.rolling_pct(df["gap_ma200"], w, mn)
    df["gsy"] = ind.gsy_flag(px, 21 * g["runup_months"], 21 * g["accel_short_months"], g["runup_min"])
    df["trend_broken"] = (df["gap_ma200"] < 0).fillna(False)
    df["drawdown"] = ind.drawdown(px)
    # DCF inversé (dernière valeur) et croissance réalisée du FCF sur 5 ans
    d = r["reverse_dcf"]
    fcf_5y = df["fcf"].shift(5 * TD)
    df["fcf_cagr_5y"] = ((df["fcf"] / fcf_5y) ** 0.2 - 1.0).where((df["fcf"] > 0) & (fcf_5y > 0))
    last = df.iloc[-1]
    df["implied_growth"] = np.nan
    df.loc[df.index[-1], "implied_growth"] = implied_growth(last["ev"], last["fcf"], d["wacc"], d["terminal_growth"], d["years"])
    # couleur
    red = (df["V"] >= r["valuation"]["red_min"]) & ((df["gap_ma200_pct"] >= r["extension"]["red_min"]) | df["gsy"])
    green = (df["V"] <= r["valuation"]["green_max"]) & df["quality_ok"]
    color = pd.Series("orange", index=cal, dtype=object)
    color[green] = "green"
    color[red] = "red"
    color[df["V"].isna()] = "orange"
    df["color"] = color
    df["color_confirmed"] = confirmed_color(df["color"], int(rules().get("confirmation_days", 5)))
    df["asset"] = key
    df.attrs["concepts"] = {k: v.attrs.get("concept") for k, v in f.items() if hasattr(v, "attrs")}
    return df


def analyse_price_only(key: str, spec: dict) -> pd.DataFrame:
    r = rules()["stocks"]
    px = yahoo.fetch_close(spec["ticker"])
    df = pd.DataFrame({"price": px})
    w, mn = TD * r["valuation"]["pct_years"], TD * r["valuation"]["pct_min_years"]
    g = r["extension"]["gsy"]
    df["gap_ma200"] = ind.gap_to_ma(px, 200)
    df["gap_ma200_pct"] = ind.rolling_pct(df["gap_ma200"], w, mn)
    df["gsy"] = ind.gsy_flag(px, 21 * g["runup_months"], 21 * g["accel_short_months"], g["runup_min"])
    df["trend_broken"] = (df["gap_ma200"] < 0).fillna(False)
    df["drawdown"] = ind.drawdown(px)
    df["V"] = np.nan
    df["color"] = "orange"            # sans valorisation, jamais rouge ni vert (règle commune)
    df["color_confirmed"] = "orange"
    df["asset"] = key
    return df


def analyse_crypto_proxy(key: str, spec: dict) -> pd.DataFrame:
    px = yahoo.fetch_close(spec["ticker"])
    btc = load_signals("btc")
    df = pd.DataFrame({"price": px})
    df["gap_ma200"] = ind.gap_to_ma(px, 200)
    df["trend_broken"] = (df["gap_ma200"] < 0).fillna(False)
    df["drawdown"] = ind.drawdown(px)
    b = btc[["color", "color_confirmed", "V", "gsy"]].reindex(btc.index.union(px.index)).ffill(limit=5).reindex(px.index)
    df["btc_color"] = b["color"]
    df["btc_V"] = b["V"]
    df["color"] = b["color"].fillna("orange")
    df["color_confirmed"] = b["color_confirmed"].fillna("orange")
    df["V"] = np.nan
    df["gsy"] = ind.gsy_flag(px, 21 * 24, 21 * 6, 1.0)
    df["asset"] = key
    return df


def compute_all() -> dict[str, pd.DataFrame]:
    out = {}
    for key, spec in watchlist().items():
        kind = spec.get("type", "operating")
        try:
            if kind == "operating":
                out[key] = analyse_operating(key, spec)
            elif kind == "crypto_proxy":
                out[key] = analyse_crypto_proxy(key, spec)
            else:
                out[key] = analyse_price_only(key, spec)
            last = out[key].iloc[-1]
            log.info("%-6s %-28s %s (brut %s) V=%s", key, spec["name"], last["color_confirmed"], last["color"],
                     "n.d." if pd.isna(last["V"]) else f"{last['V']:.0f}")
        except Exception as exc:  # noqa: BLE001
            log.error("%s : échec (%s)", key, exc)
    return out


def save_all(res: dict[str, pd.DataFrame]) -> None:
    (SIGNALS_DIR / "stocks").mkdir(exist_ok=True)
    latest = {}
    for key, df in res.items():
        df.to_parquet(SIGNALS_DIR / "stocks" / f"{key}.parquet")
        last = df.iloc[-1]
        latest[key] = {k: (None if isinstance(v, float) and np.isnan(v) else (v.item() if hasattr(v, "item") else v))
                       for k, v in last.items() if k != "asset"}
        latest[key]["date"] = str(df.index[-1].date())
        latest[key]["concepts"] = df.attrs.get("concepts", {})
    (DOCS_DIR / "stocks_latest.json").write_text(json.dumps(latest, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


def load_all() -> dict[str, pd.DataFrame]:
    d = SIGNALS_DIR / "stocks"
    if not d.exists():
        return {}
    return {p.stem: pd.read_parquet(p) for p in sorted(d.glob("*.parquet"))}
