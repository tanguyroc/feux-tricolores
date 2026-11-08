"""Familles d'indicateurs et couleurs, point-in-time, pour les indices et le Bitcoin."""
from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from . import indicators as ind
from . import store
from .config import DATA_DIR, DOCS_DIR, rules

log = logging.getLogger("feux.signals")
SIGNALS_DIR = DATA_DIR / "signals"
SIGNALS_DIR.mkdir(parents=True, exist_ok=True)

TD = ind.TRADING_DAYS_PER_YEAR


def _nanmedian(cols: list[pd.Series]) -> pd.Series:
    df = pd.concat(cols, axis=1)
    return df.median(axis=1, skipna=True)


# ----------------------------------------------------------------------------------------------
# Valorisation commune (S&P 500, Shiller) — mensuel, puis « vivant » au quotidien
# ----------------------------------------------------------------------------------------------
def common_valuation(calendar: pd.DatetimeIndex, px_daily: pd.Series) -> pd.DataFrame:
    r = rules()
    w = r["windows"]
    lag_m = int(r["lags"]["shiller_earnings_months"])
    P = store.to_indexed(store.load("shiller_P"))
    E = store.to_indexed(store.load("shiller_E"))
    CPI = store.to_indexed(store.load("shiller_CPI"))
    GS10 = store.to_indexed(store.load("shiller_GS10"))
    m = pd.concat({"P": P, "E": E, "CPI": CPI, "GS10": GS10}, axis=1).sort_index()
    m["cape"] = ind.cape_pit(m["P"], m["E"], m["CPI"], lag_m)
    m["ecy"] = ind.excess_cape_yield(m["cape"], m["GS10"], m["CPI"])
    m = m.dropna(subset=["cape"])

    win_m, min_m = 12 * w["pct_years"], 12 * w["pct_min_years"]
    # valeurs mensuelles disponibles en fin de mois -> dernière valeur connue à chaque jour
    cape_m = store.make_series(m.index, m["cape"])
    ecy_m = store.make_series(m.index, m["ecy"])
    P_m = store.make_series(m.index, m["P"])
    infl = (m["CPI"] / m["CPI"].shift(120)) ** 0.1 - 1.0
    real_rate_m = store.make_series(m.index, m["GS10"] / 100.0 - infl)

    out = pd.DataFrame(index=calendar)
    cape_last = store.as_of(cape_m, calendar)
    p_last = store.as_of(P_m, calendar)
    rr_last = store.as_of(real_rate_m, calendar)
    # CAPE « vivant » : CAPE du dernier mois connu, rescalé par prix du jour / prix moyen de ce mois
    out["cape_live"] = cape_last * (px_daily.reindex(calendar) / p_last)
    out["ecy_live"] = 1.0 / out["cape_live"] - rr_last
    out["cape_pct"] = ind.pct_against_reference(out["cape_live"], m["cape"], win_m, min_m)
    out["ecy_pct_inv"] = ind.pct_against_reference(-out["ecy_live"], -m["ecy"], win_m, min_m)

    # AIAE trimestriel (Z.1), percentile sur 25 ans = 100 trimestres, minimum 60
    aiae = store.load("aiae")
    aiae_q = store.to_indexed(aiae)
    aiae_pct_q = ind.rolling_pct(aiae_q, 4 * w["pct_years"], 4 * w["pct_min_years"])
    out["aiae"] = store.as_of(aiae, calendar)
    out["aiae_pct"] = store.as_of(store.make_series(aiae.ref_date, aiae_pct_q.reindex(aiae_q.index).to_numpy(),
                                                    available_dates=aiae.available_date, dropna=False), calendar)
    out["V"] = _nanmedian([out["cape_pct"], out["ecy_pct_inv"], out["aiae_pct"]])
    return out


def common_euphoria(calendar: pd.DatetimeIndex) -> pd.DataFrame:
    r = rules()
    md = store.load("margin_debt")
    s = store.to_indexed(md)
    yoy = s / s.shift(12) - 1.0
    pct = ind.expanding_pct(yoy, 12 * r["windows"]["margin_expanding_min_years"])
    extreme = yoy >= r["indices"]["euphoria"]["margin_debt_yoy_extreme"]
    e_val = pct.where(~extreme, 100.0)
    out = pd.DataFrame(index=calendar)
    out["margin_yoy"] = store.as_of(store.make_series(md.ref_date, yoy.reindex(s.index).to_numpy(),
                                                      available_dates=md.available_date), calendar)
    out["E"] = store.as_of(store.make_series(md.ref_date, e_val.reindex(s.index).to_numpy(),
                                             available_dates=md.available_date, dropna=False), calendar)
    return out


def common_fear(calendar: pd.DatetimeIndex) -> pd.DataFrame:
    w = rules()["windows"]
    out = pd.DataFrame(index=calendar)
    cols = []
    for name in ["vix", "credit_spread"]:
        s = store.to_indexed(store.load(name))
        pct = ind.rolling_pct(s, TD * w["pct_years"], TD * w["pct_min_years_fast"])
        df = store.make_series(s.index, s.values)
        out[name] = store.as_of(df, calendar)
        out[f"{name}_pct"] = store.as_of(store.make_series(s.index, pct.to_numpy(), dropna=False), calendar)
        cols.append(out[f"{name}_pct"])
    out["P"] = _nanmedian(cols)
    return out


# ----------------------------------------------------------------------------------------------
# Indices
# ----------------------------------------------------------------------------------------------
def index_signals(key: str, common: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    r = rules()
    w, xr = r["windows"], r["indices"]["extension"]
    px = store.to_indexed(store.load(f"px_{key}"))
    px = px[~px.index.duplicated()].sort_index()
    cal = px.index
    df = pd.DataFrame({"price": px})

    # famille X
    df["gap_ma200"] = ind.gap_to_ma(px, 200)
    df["mom_12m"] = ind.momentum(px, TD)
    df["gap_ma200_pct"] = ind.rolling_pct(df["gap_ma200"], TD * w["pct_years"], TD * w["pct_min_years"])
    df["mom_12m_pct"] = ind.rolling_pct(df["mom_12m"], TD * w["pct_years"], TD * w["pct_min_years"])
    g = xr["gsy"]
    df["gsy"] = ind.gsy_flag(px, 21 * g["runup_months"], 21 * g["accel_short_months"], g["runup_min"])
    df["X"] = _nanmedian([df["gap_ma200_pct"], df["mom_12m_pct"]]).where(~df["gsy"], 100.0)
    df["drawdown"] = ind.drawdown(px)

    # familles communes (valorisation S&P 500, euphorie US, peur)
    if common is None:
        common = {}
    if "V" not in common:
        sp = store.to_indexed(store.load("px_sp500"))
        common["V"] = common_valuation(cal, sp if key == "sp500" else sp.reindex(cal, method="ffill"))
    if "E" not in common:
        common["E"] = common_euphoria(cal)
    if "P" not in common:
        common["P"] = common_fear(cal)
    for part in ("V", "E", "P"):
        # calendriers différents (MSCI World publie certains jours fériés US) : dernière valeur connue, ≤ 7 jours
        c = common[part].reindex(common[part].index.union(cal)).ffill(limit=7).reindex(cal)
        for col in c.columns:
            df[col] = c[col]

    # drapeaux de tendance (mensuels, connus en fin de mois, appliqués ensuite)
    fk = r["indices"]["falling_knife"]
    broken_m = ind.sma_month_flag(px, r["indices"]["leverage_flag"]["sma_months"])
    broken = store.make_series(broken_m.index, broken_m.astype(float).to_numpy())
    df["trend_broken"] = store.as_of(broken, cal).fillna(0.0).astype(bool)
    mclose = ind.monthly_closes(px)
    below_sma = (mclose < mclose.rolling(fk["sma_months"], min_periods=fk["sma_months"]).mean())
    mom3 = mclose / mclose.shift(fk["mom_months"]) - 1.0
    knife_m = (below_sma & (mom3 < 0)).astype(float)
    df["falling_knife_cond"] = store.as_of(store.make_series(knife_m.index, knife_m.to_numpy()), cal).fillna(0.0).astype(bool)

    df = _colorize_index(df)
    df["asset"] = key
    return df


def _colorize_index(df: pd.DataFrame) -> pd.DataFrame:
    r = rules()["indices"]
    V, X, E, P = df["V"], df["X"], df["E"], df["P"]
    red = (V >= r["valuation"]["red_min"]) & (
        (X >= r["extension"]["red_min"]) | (E >= r["euphoria"]["red_min"]) | df["gsy"])
    green_cap = (df["drawdown"] >= r["fear"]["drawdown_min"]) & (P >= r["fear"]["green_min"])
    green_val = V <= r["valuation"]["green_max"]
    color = pd.Series("orange", index=df.index, dtype=object)
    reason = pd.Series("", index=df.index, dtype=object)
    color[green_val] = "green"; reason[green_val] = "valorisation basse (V ≤ 40)"
    color[red] = "red"
    reason[red] = "cher (V ≥ 80) et " + np.where(df["gsy"][red], "hausse ≥100 %/2 ans avec accélération",
                                                np.where(X[red] >= r["extension"]["red_min"], "extension (X ≥ 90)", "euphorie (dette sur marge, E ≥ 80)"))
    color[green_cap] = "green"
    reason[green_cap] = "capitulation (baisse ≥ 25 % et peur P ≥ 80)"
    color[V.isna() & ~green_cap] = "orange"
    df["color"] = color
    df["reason"] = reason
    df["falling_knife"] = (df["color"] == "green") & df["falling_knife_cond"]
    return df


# ----------------------------------------------------------------------------------------------
# Bitcoin
# ----------------------------------------------------------------------------------------------
def bitcoin_signals() -> pd.DataFrame:
    r = rules()
    w, b = r["windows"], r["bitcoin"]
    px = store.to_indexed(store.load("btc_price"))
    mvrv = store.to_indexed(store.load("btc_mvrv"))
    cal = px.index
    df = pd.DataFrame({"price": px})
    df["mvrv"] = mvrv.reindex(cal).ffill(limit=3)   # MVRV publié avec un jour de retard sur le prix
    df["ma200w"] = px.rolling(1400, min_periods=1400).mean()          # 200 semaines ≈ 1400 jours calendaires
    df["ratio_200w"] = px / df["ma200w"]
    zw, zmin = 365 * w["btc_z_years"], 365 * w["btc_z_min_years"]
    df["z_ratio_200w"] = ind.rolling_z(np.log(df["ratio_200w"]), zw, zmin)
    df["z_mvrv"] = ind.rolling_z(np.log(df["mvrv"]), zw, zmin)
    df["V"] = df[["z_ratio_200w", "z_mvrv"]].mean(axis=1, skipna=True)
    g = b["extension"]["gsy"]
    df["gsy"] = ind.gsy_flag(px, int(30.4 * g["runup_months"]), int(30.4 * g["accel_short_months"]), g["runup_min"])
    df["drawdown"] = ind.drawdown(px)
    df["gap_ma200d"] = ind.gap_to_ma(px, b["leverage_flag"]["sma_days"])
    df["trend_broken"] = (df["gap_ma200d"] < 0).fillna(False)
    fng = store.load("btc_fng")
    fng_s = store.to_indexed(fng)
    df["fng"] = store.as_of(fng, cal)
    df["fng_30d"] = store.as_of(store.make_series(fng_s.index, fng_s.rolling(30, min_periods=20).mean().to_numpy(), dropna=False), cal)

    red = (df["V"] >= b["valuation"]["red_min_z"]) & df["gsy"]
    green_cap = (df["drawdown"] >= b["capitulation"]["drawdown_min"]) & (df["fng_30d"] <= b["capitulation"]["fng_30d_max"])
    green_val = df["V"] <= b["valuation"]["green_max_z"]
    color = pd.Series("orange", index=cal, dtype=object)
    reason = pd.Series("", index=cal, dtype=object)
    color[green_val] = "green"; reason[green_val] = "valorisation basse (z ≤ −0,5)"
    color[red] = "red"; reason[red] = "cher (z ≥ 1,5) et hausse ≥100 %/2 ans avec accélération"
    color[green_cap] = "green"; reason[green_cap] = "capitulation (baisse ≥ 50 % et peur extrême 30 j)"
    color[df["V"].isna() & ~green_cap] = "orange"
    df["color"], df["reason"] = color, reason
    df["falling_knife"] = (df["color"] == "green") & df["trend_broken"]
    df["asset"] = "btc"
    return df


# ----------------------------------------------------------------------------------------------
def compute_all() -> dict[str, pd.DataFrame]:
    r = rules()
    res = {}
    sp = store.to_indexed(store.load("px_sp500"))
    common = {"V": common_valuation(sp.index, sp), "E": common_euphoria(sp.index), "P": common_fear(sp.index)}
    for key in r["indices"]["assets"]:
        res[key] = index_signals(key, common={k: v for k, v in common.items()})
        log.info("%s : %d jours, dernier %s = %s", key, len(res[key]), res[key].index[-1].date(), res[key]["color"].iloc[-1])
    res["btc"] = bitcoin_signals()
    log.info("btc : %d jours, dernier %s = %s", len(res["btc"]), res["btc"].index[-1].date(), res["btc"]["color"].iloc[-1])
    return res


def save_signals(res: dict[str, pd.DataFrame]) -> None:
    latest = {}
    for key, df in res.items():
        df.to_parquet(SIGNALS_DIR / f"{key}.parquet")
        last = df.iloc[-1]
        latest[key] = {k: (None if (isinstance(v, float) and np.isnan(v)) else (v.item() if hasattr(v, "item") else v))
                       for k, v in last.items() if k not in ("asset",)}
        latest[key]["date"] = str(df.index[-1].date())
    (DOCS_DIR / "latest.json").write_text(json.dumps(latest, indent=1, default=str, ensure_ascii=False), encoding="utf-8")


def load_signals(key: str) -> pd.DataFrame:
    return pd.read_parquet(SIGNALS_DIR / f"{key}.parquet")
