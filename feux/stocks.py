"""Module actions : univers Top 100 mondial (+ compléments de stocks.yaml).

Pour chaque société :
- toujours : extension de prix (écart MM200 en percentile 10 ans), critère de bulle GSY, tendance, baisse depuis le plus haut ;
- si ses comptes sont dans EDGAR (CIK) : valorisation point-in-time (EV/EBIT, P/FCF en percentile 10 ans), DCF inversé,
  filtre qualité éliminatoire, couleur. Sinon : « prix seul », jamais rouge ni vert (pas de valorisation) ;
- proxys crypto : suivent le feu Bitcoin et leur propre tendance.
Les prix sont convertis dans la devise des comptes quand elles diffèrent (ex. Shell : cours en pence, comptes en dollars).
"""
from __future__ import annotations

import json
import logging
import time

import numpy as np
import pandas as pd
import yaml

from . import indicators as ind
from . import store
from .config import DOCS_DIR, ROOT, rules
from .loaders import edgar, log as loader_log, yahoo
from .signals import SIGNALS_DIR, confirmed_color, load_signals

log = logging.getLogger("feux.stocks")
STOCKS_PATH = ROOT / "stocks.yaml"
TD = 252
_FX_CACHE: dict[str, pd.Series] = {}


def extras() -> dict:
    """Compléments / surcharges de stocks.yaml (type crypto_proxy, valeurs hors Top 100...)."""
    if not STOCKS_PATH.exists():
        return {}
    with open(STOCKS_PATH, encoding="utf-8") as fh:
        wl = yaml.safe_load(fh).get("stocks", {}) or {}
    return {str(k): v for k, v in wl.items()}


# ----------------------------------------------------------------------------------------------
def _asof(df: pd.DataFrame, cal: pd.DatetimeIndex) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(np.nan, index=cal)
    s = store.make_series(df["end"], df["val"], available_dates=df["filed"])
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


def fx_series(from_ccy: str, to_ccy: str, cal: pd.DatetimeIndex) -> pd.Series:
    """Taux de change quotidien from->to (Yahoo « EURUSD=X »), avec gestion des pence (GBp)."""
    scale = 1.0
    if from_ccy == "GBp":
        from_ccy, scale = "GBP", 0.01
    if from_ccy == to_ccy:
        return pd.Series(scale, index=cal)
    key = f"{from_ccy}{to_ccy}=X"
    if key not in _FX_CACHE:
        _FX_CACHE[key] = yahoo.fetch_close(key)
        time.sleep(0.5)
    fx = _FX_CACHE[key].reindex(_FX_CACHE[key].index.union(cal)).ffill().reindex(cal)
    return fx * scale


def price_block(px: pd.Series) -> pd.DataFrame:
    r = rules()["stocks"]
    w, mn = TD * r["valuation"]["pct_years"], TD * r["valuation"]["pct_min_years"]
    g = r["extension"]["gsy"]
    df = pd.DataFrame({"price": px})
    df["gap_ma200"] = ind.gap_to_ma(px, 200)
    df["gap_ma200_pct"] = ind.rolling_pct(df["gap_ma200"], w, mn)
    df["runup_24m"] = ind.momentum(px, 21 * g["runup_months"])
    df["gsy"] = ind.gsy_flag(px, 21 * g["runup_months"], 21 * g["accel_short_months"], g["runup_min"])
    df["trend_broken"] = (df["gap_ma200"] < 0).fillna(False)
    df["drawdown"] = ind.drawdown(px)
    df["mom_12m"] = ind.momentum(px, TD)
    return df


def analyse_operating(key: str, spec: dict) -> pd.DataFrame:
    r = rules()["stocks"]
    px, px_ccy = yahoo.fetch_close_meta(spec["ticker"])
    cal = px.index
    f = edgar.fundamentals(int(spec["cik"]))
    df = price_block(px)
    unit = next((v.attrs.get("unit") for v in f.values() if v.attrs.get("unit") and v.attrs.get("unit") != "shares"), px_ccy)
    df["price_in_accounts_ccy"] = px * fx_series(px_ccy, unit, cal) if unit and px_ccy and unit != px_ccy else px
    for k in ("revenue", "ebit", "net_income", "cfo", "capex", "da", "cash", "st_investments", "debt_lt", "debt_st", "equity", "shares"):
        df[k] = _asof(f.get(k), cal)
    df["fcf"] = df["cfo"] - df["capex"].fillna(0.0)
    df["debt"] = df["debt_lt"].fillna(0.0) + df["debt_st"].fillna(0.0)
    df["liquidity"] = df["cash"].fillna(0.0) + df["st_investments"].fillna(0.0)
    df["mcap"] = df["price_in_accounts_ccy"] * df["shares"]
    df["ev"] = df["mcap"] + df["debt"] - df["liquidity"]
    df["ev_ebit"] = (df["ev"] / df["ebit"]).where(df["ebit"] > 0)
    df["p_fcf"] = (df["mcap"] / df["fcf"]).where(df["fcf"] > 0)
    w, mn = TD * r["valuation"]["pct_years"], TD * r["valuation"]["pct_min_years"]
    df["ev_ebit_pct"] = ind.rolling_pct(df["ev_ebit"], w, mn)
    df["p_fcf_pct"] = ind.rolling_pct(df["p_fcf"], w, mn)
    df["V"] = df[["ev_ebit_pct", "p_fcf_pct"]].median(axis=1, skipna=True)
    q = r["quality"]
    invested = df["equity"] + df["debt"] - df["liquidity"]
    df["roic"] = (df["ebit"] * (1 - q["tax_rate"]) / invested).where(invested > 0)
    df["fcf_ni"] = (df["fcf"] / df["net_income"]).where(df["net_income"] > 0)
    ebitda = df["ebit"] + df["da"].fillna(0.0)
    df["nd_ebitda"] = ((df["debt"] - df["liquidity"]) / ebitda).where(ebitda > 0)
    df["quality_ok"] = (df["roic"] >= q["roic_min"]) & (df["fcf_ni"] >= q["fcf_to_net_income_min"]) & (df["nd_ebitda"] <= q["net_debt_to_ebitda_max"])
    d = r["reverse_dcf"]
    fcf_5y = df["fcf"].shift(5 * TD)
    df["fcf_cagr_5y"] = ((df["fcf"] / fcf_5y) ** 0.2 - 1.0).where((df["fcf"] > 0) & (fcf_5y > 0))
    last = df.iloc[-1]
    df["implied_growth"] = np.nan
    df.loc[df.index[-1], "implied_growth"] = implied_growth(last["ev"], last["fcf"], d["wacc"], d["terminal_growth"], d["years"])
    red = (df["V"] >= r["valuation"]["red_min"]) & ((df["gap_ma200_pct"] >= r["extension"]["red_min"]) | df["gsy"])
    green = (df["V"] <= r["valuation"]["green_max"]) & df["quality_ok"]
    color = pd.Series("orange", index=cal, dtype=object)
    color[green] = "green"
    color[red] = "red"
    color[df["V"].isna()] = "orange"
    df["color"] = color
    df["color_confirmed"] = confirmed_color(df["color"], int(rules().get("confirmation_days", 5)))
    df["kind"] = "operating"
    df.attrs["concepts"] = {k: v.attrs.get("concept") for k, v in f.items() if hasattr(v, "attrs")}
    df.attrs["accounts_currency"] = unit
    df.attrs["price_currency"] = px_ccy
    return df


def analyse_price_only(key: str, spec: dict) -> pd.DataFrame:
    px = yahoo.fetch_close(spec["ticker"])
    df = price_block(px)
    df["V"] = np.nan
    df["color"] = "orange"
    df["color_confirmed"] = "orange"
    df["kind"] = "price_only"
    return df


def analyse_crypto_proxy(key: str, spec: dict) -> pd.DataFrame:
    px = yahoo.fetch_close(spec["ticker"])
    btc = load_signals("btc")
    df = price_block(px)
    b = btc[["color", "color_confirmed", "V"]].reindex(btc.index.union(px.index)).ffill(limit=5).reindex(px.index)
    df["btc_color"] = b["color"]
    df["color"] = b["color"].fillna("orange")
    df["color_confirmed"] = b["color_confirmed"].fillna("orange")
    df["V"] = np.nan
    df["kind"] = "crypto_proxy"
    return df


# ----------------------------------------------------------------------------------------------
def targets() -> list[dict]:
    """Univers Top 100 (data/universe.csv) + compléments de stocks.yaml. Les surcharges de stocks.yaml
    (par symbole) l'emportent : type, nom, cik."""
    from .universe import UNIVERSE_CSV, load

    ex = extras()
    out, seen = [], set()
    if UNIVERSE_CSV.exists():
        u = load()
        for row in u.itertuples():
            if not isinstance(row.symbol, str):
                continue
            spec = {"key": row.symbol, "name": row.name, "ticker": row.symbol, "country": row.country, "sector": row.sector,
                    "industry": row.industry, "weight": float(row.weight), "rank": int(row.rank), "pea": bool(row.pea_eligible_approx),
                    "cik": None if pd.isna(row.cik) else int(row.cik), "type": "operating" if not pd.isna(row.cik) else "price_only",
                    "source": "top100"}
            over = next((v for v in ex.values() if v.get("ticker") == row.symbol), None)
            if over:
                spec.update({k: over[k] for k in ("type", "cik", "name") if k in over})
            out.append(spec)
            seen.add(row.symbol)
    for k, v in ex.items():
        if v.get("ticker") in seen:
            continue
        out.append({"key": k, "name": v.get("name", k), "ticker": v["ticker"], "country": v.get("country"), "sector": v.get("sector"),
                    "industry": None, "weight": None, "rank": None, "pea": v.get("pea"), "cik": v.get("cik"),
                    "type": v.get("type", "operating" if v.get("cik") else "price_only"), "source": "stocks.yaml"})
    return out


def compute_all(limit: int | None = None) -> dict[str, pd.DataFrame]:
    import os

    out = {}
    specs = targets()[:limit] if limit else targets()
    sec_ok = "@" in os.environ.get("SEC_USER_AGENT", "")
    if not sec_ok:
        log.warning("SEC_USER_AGENT absent : toutes les sociétés sont analysées en prix seul (pas de valorisation ni de qualité)")
    n_ok = n_fail = 0
    for spec in specs:
        kind = spec["type"]
        try:
            if kind == "operating" and spec.get("cik") and sec_ok:
                df = analyse_operating(spec["key"], spec)
            elif kind == "crypto_proxy":
                df = analyse_crypto_proxy(spec["key"], spec)
            else:
                df = analyse_price_only(spec["key"], spec)
            for k in ("name", "country", "sector", "industry", "weight", "rank", "pea", "source", "ticker"):
                df.attrs[k] = spec.get(k)
            out[spec["key"]] = df
            n_ok += 1
        except Exception as exc:  # noqa: BLE001
            log.error("%s (%s) : échec — %s", spec["key"], spec["name"], str(exc)[:160])
            n_fail += 1
        time.sleep(0.6)
    log.info("Actions : %d analysées, %d en échec ; %d avec comptes EDGAR", n_ok, n_fail, sum(1 for d in out.values() if d["kind"].iloc[-1] == "operating"))
    return out


def save_all(res: dict[str, pd.DataFrame]) -> None:
    d = SIGNALS_DIR / "stocks"
    d.mkdir(exist_ok=True)
    for old in d.glob("*.parquet"):
        old.unlink()
    latest = {}
    for key, df in res.items():
        safe = key.replace("/", "_")
        df.to_parquet(d / f"{safe}.parquet")
        last = df.iloc[-1]
        rec = {k: (None if isinstance(v, float) and np.isnan(v) else (v.item() if hasattr(v, "item") else v)) for k, v in last.items()}
        rec.update({k: v for k, v in df.attrs.items()})
        rec["date"] = str(df.index[-1].date())
        rec["since"] = _since(df)
        latest[key] = rec
    (DOCS_DIR / "stocks_latest.json").write_text(json.dumps(latest, indent=0, ensure_ascii=False, default=str), encoding="utf-8")


def _since(df: pd.DataFrame) -> str:
    col = df["color_confirmed"]
    last = col.iloc[-1]
    changes = col[col != last]
    start = col.index[0] if changes.empty else col.index[col.index.get_loc(changes.index[-1]) + 1]
    return str(start.date())


def load_latest() -> dict:
    p = DOCS_DIR / "stocks_latest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
