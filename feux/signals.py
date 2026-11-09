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
    # le CAPE d'un mois exige l'indice des prix de ce mois, publié vers le 15 du mois suivant (v1.0.1 : jusqu'ici le CAPE
    # était utilisé dès la fin du mois, deux semaines trop tôt) : disponibilité = fin de mois + 15 jours, pour le CAPE,
    # le prix moyen du même mois (qui sert à l'actualiser) et le taux réel
    cpi_lag = pd.Timedelta(days=15)
    avail = m.index + cpi_lag
    cape_m = store.make_series(m.index, m["cape"], available_dates=avail)
    ecy_m = store.make_series(m.index, m["ecy"], available_dates=avail)
    P_m = store.make_series(m.index, m["P"], available_dates=avail)
    infl = (m["CPI"] / m["CPI"].shift(120)) ** 0.1 - 1.0
    real_rate_m = store.make_series(m.index, m["GS10"] / 100.0 - infl, available_dates=avail)
    m_av = m.set_axis(avail)     # historique de référence indexé par date de disponibilité

    out = pd.DataFrame(index=calendar)
    cape_last = store.as_of(cape_m, calendar)
    p_last = store.as_of(P_m, calendar)
    rr_last = store.as_of(real_rate_m, calendar)
    # CAPE « vivant » : CAPE du dernier mois connu, rescalé par prix du jour / prix moyen de ce mois
    out["cape_live"] = cape_last * (px_daily.reindex(calendar) / p_last)
    out["ecy_live"] = 1.0 / out["cape_live"] - rr_last
    out["cape_pct"] = ind.pct_against_reference(out["cape_live"], m_av["cape"], win_m, min_m)
    out["ecy_pct_inv"] = ind.pct_against_reference(-out["ecy_live"], -m_av["ecy"], win_m, min_m)

    # AIAE trimestriel (Z.1), percentile sur 25 ans = 100 trimestres, minimum 60
    aiae = store.load("aiae")
    aiae_q = store.to_indexed(aiae)
    aiae_pct_q = ind.rolling_pct(aiae_q, 4 * w["pct_years"], 4 * w["pct_min_years"])
    out["aiae"] = store.as_of(aiae, calendar)
    out["aiae_pct"] = store.as_of(store.make_series(aiae.ref_date, aiae_pct_q.reindex(aiae_q.index).to_numpy(),
                                                    available_dates=aiae.available_date, dropna=False), calendar)
    # v1.0 : V = percentile du CAPE parmi TOUTES les valeurs mensuelles depuis 1881 (fenêtre croissante, minimum 30 ans)
    vr = r["indices"]["valuation"]
    out["V"] = ind.pct_against_reference(out["cape_live"], m_av["cape"], 10 ** 7, int(vr["min_months"]))
    out["V_25y"] = _nanmedian([out["cape_pct"], out["ecy_pct_inv"], out["aiae_pct"]])   # ancienne V (v0.x), contexte
    # rendement réel attendu à 10 ans (CAPE), modèle réestimé chaque mois avec les seules issues connues à la date
    model = expected_return_model(m)
    for col in ("er_a", "er_b", "er_q10", "er_q90", "er_n_decades"):
        out[col] = store.as_of(store.make_series(model.index, model[col].to_numpy(), available_dates=model.index + cpi_lag, dropna=False), calendar)
    out["er10"] = out["er_a"] + out["er_b"] * np.log(out["cape_live"])
    out["er10_lo"] = out["er10"] + out["er_q10"]
    out["er10_hi"] = out["er10"] + out["er_q90"]
    return out


def real_total_return_index(m: pd.DataFrame) -> pd.Series:
    """Indice de rendement total réel (dividendes réinvestis, déflaté par le CPI), comme la colonne de Shiller."""
    D = store.to_indexed(store.load("shiller_D")).reindex(m.index)
    gross = (m["P"] + D / 12.0) / m["P"].shift(1) * (m["CPI"].shift(1) / m["CPI"])
    return gross.fillna(1.0).cumprod()


def expected_return_model(m: pd.DataFrame, min_months: int = 360) -> pd.DataFrame:
    """Régression rendement réel annualisé 10 ans ~ ln(CAPE), réestimée chaque mois t avec les mois s tels que s + 120 ≤ t.
    Renvoie a, b et les quantiles 10 % / 90 % des résidus (fourchette 80 %), indexés par mois de disponibilité."""
    tr = real_total_return_index(m)
    y = (tr.shift(-120) / tr) ** 0.1 - 1.0
    lc = np.log(m["cape"])
    d = pd.DataFrame({"y": y, "lc": lc}).dropna()
    rows = []
    for t in m.index:
        known = d[d.index <= t - pd.DateOffset(months=120)]
        if len(known) < min_months:
            continue
        X = np.column_stack([np.ones(len(known)), known["lc"].to_numpy()])
        coef, *_ = np.linalg.lstsq(X, known["y"].to_numpy(), rcond=None)
        res = known["y"].to_numpy() - X @ coef
        rows.append((t, coef[0], coef[1], np.quantile(res, 0.10), np.quantile(res, 0.90), len(known) / 120.0))
    return pd.DataFrame(rows, columns=["t", "er_a", "er_b", "er_q10", "er_q90", "er_n_decades"]).set_index("t")


def common_euphoria(calendar: pd.DatetimeIndex) -> pd.DataFrame:
    r = rules()
    md = store.load("margin_debt")
    s = store.to_indexed(md)
    yoy = s / s.shift(12) - 1.0
    pct = ind.expanding_pct(yoy, 12 * r["windows"]["margin_expanding_min_years"])
    extreme = yoy >= r["indices"]["context"]["euphoria"]["margin_debt_yoy_extreme"]
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
        # VIX : connu à la clôture du jour ; écart Baa − 10 ans (FRED BAA10Y) : publié le jour ouvré suivant (v1.0.1)
        av = s.index + (pd.offsets.BDay(1) if name == "credit_spread" else pd.Timedelta(0))
        df = store.make_series(s.index, s.values, available_dates=av)
        out[name] = store.as_of(df, calendar)
        out[f"{name}_pct"] = store.as_of(store.make_series(s.index, pct.to_numpy(), available_dates=av, dropna=False), calendar)
        cols.append(out[f"{name}_pct"])
    out["P"] = _nanmedian(cols)
    return out


# ----------------------------------------------------------------------------------------------
# Indices
# ----------------------------------------------------------------------------------------------
def index_signals(key: str, common: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    r = rules()
    w, xr = r["windows"], r["indices"]["context"]["extension"]
    px = store.to_indexed(store.load(f"px_{key}"))
    px = px[~px.index.duplicated()].sort_index()
    px = px[px.index.dayofweek < 5]     # barre fictive du dimanche (MSCI World, Yahoo) : écartée (v1.0.1)
    cal = px.index
    df = pd.DataFrame({"price": px})

    # famille X
    df["gap_ma200"] = ind.gap_to_ma(px, 200)
    df["mom_12m"] = ind.momentum(px, TD)
    df["gap_ma200_pct"] = ind.rolling_pct(df["gap_ma200"], TD * w["pct_years"], TD * w["pct_min_years"])
    df["mom_12m_pct"] = ind.rolling_pct(df["mom_12m"], TD * w["pct_years"], TD * w["pct_min_years"])
    g = xr["gsy"]
    df["gsy"] = ind.gsy_flag(px, 21 * g["runup_months"], 21 * g["accel_short_months"], g["runup_min"])
    df["X"] = _nanmedian([df["gap_ma200_pct"], df["mom_12m_pct"]]).where(~df["gsy"], 100.0)   # contexte (v0.x)
    ct = r["indices"]["context"]["cher_tendu"]
    df["x_hist_pct"] = ind.pct_against_reference(df["gap_ma200"], df["gap_ma200"].dropna(), 10 ** 7, TD * int(ct["x_min_years"]))
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
    # clôture du dernier jour du mois connue le soir même : drapeau appliqué à partir du jour suivant (pas de fuite d'un jour)
    broken = store.make_series(broken_m.index, broken_m.astype(float).to_numpy(), lag=pd.Timedelta(days=1))
    df["trend_broken"] = store.as_of(broken, cal).fillna(0.0).astype(bool)
    mclose = ind.monthly_closes(px)
    below_sma = (mclose < mclose.rolling(fk["sma_months"], min_periods=fk["sma_months"]).mean())
    mom3 = mclose / mclose.shift(fk["mom_months"]) - 1.0
    knife_m = (below_sma & (mom3 < 0)).astype(float)
    df["falling_knife_cond"] = store.as_of(store.make_series(knife_m.index, knife_m.to_numpy(), lag=pd.Timedelta(days=1)), cal).fillna(0.0).astype(bool)

    df = _colorize_index(df)
    df["asset"] = key
    return df


def _colorize_index(df: pd.DataFrame) -> pd.DataFrame:
    """v1.0 (protocole §8.4) : vert = valorisation basse ou capitulation ; sinon orange. « Cher » est une information."""
    r = rules()["indices"]
    V, P = df["V"], df["P"]
    green_cap = (df["drawdown"] >= r["fear"]["drawdown_min"]) & (P >= r["fear"]["green_min"])
    green_val = V <= r["valuation"]["green_max"]
    color = pd.Series("orange", index=df.index, dtype=object)
    reason = pd.Series("", index=df.index, dtype=object)
    color[green_val] = "green"; reason[green_val] = "valorisation basse (V ≤ 40)"
    color[green_cap] = "green"; reason[green_cap] = "capitulation (baisse ≥ 25 % et peur P ≥ 80)"
    df["cher"] = (V >= r["valuation"]["cher_min"]).fillna(False)
    ct = r["context"]["cher_tendu"]
    df["cher_tendu"] = ((V >= ct["v_min"]) & (df["x_hist_pct"] >= ct["x_min"])).fillna(False)
    orange = color == "orange"
    reason[orange & df["cher"]] = "cher (V ≥ 80) : information, pas de règle de report"
    reason[orange & df["cher_tendu"]] = "cher et tendu (V ≥ 80, écart MM200 ≥ 90e percentile) : information, pas de règle de report"
    df["color"] = color
    df["reason"] = reason
    df["falling_knife"] = (df["color"] == "green") & df["falling_knife_cond"]
    return df


# ----------------------------------------------------------------------------------------------
# Bitcoin
# ----------------------------------------------------------------------------------------------
def bitcoin_signals() -> pd.DataFrame:
    """v1.0, règle B1 : vert si MVRV < 1 ou prix < moyenne 200 semaines ; rouge si MVRV ≥ 3 ; orange sinon.
    z-scores, critère GSY, financement et Fear & Greed : contexte."""
    r = rules()
    b = r["bitcoin"]
    ctx = b["context"]
    px = store.to_indexed(store.load("btc_price"))
    mvrv = store.to_indexed(store.load("btc_mvrv"))
    cal = px.index
    df = pd.DataFrame({"price": px})
    df["mvrv"] = mvrv.reindex(cal).ffill(limit=3)   # MVRV publié avec un jour de retard sur le prix
    df["ma200w"] = px.rolling(1400, min_periods=1400).mean()          # 200 semaines ≈ 1400 jours calendaires
    df["ratio_200w"] = px / df["ma200w"]
    zw, zmin = 365 * ctx["z"]["years"], 365 * ctx["z"]["min_years"]
    df["z_ratio_200w"] = ind.rolling_z(np.log(df["ratio_200w"]), zw, zmin)
    df["z_mvrv"] = ind.rolling_z(np.log(df["mvrv"]), zw, zmin)
    df["V"] = df[["z_ratio_200w", "z_mvrv"]].mean(axis=1, skipna=True)   # ancienne V (v0.x), contexte
    g = ctx["gsy"]
    df["gsy"] = ind.gsy_flag(px, int(30.4 * g["runup_months"]), int(30.4 * g["accel_short_months"]), g["runup_min"])
    df["drawdown"] = ind.drawdown(px)
    df["gap_ma200d"] = ind.gap_to_ma(px, b["leverage_flag"]["sma_days"])
    df["trend_broken"] = (df["gap_ma200d"] < 0).fillna(False)
    fng = store.load("btc_fng")
    fng_s = store.to_indexed(fng)
    df["fng"] = store.as_of(fng, cal)
    df["fng_30d"] = store.as_of(store.make_series(fng_s.index, fng_s.rolling(30, min_periods=20).mean().to_numpy(), dropna=False), cal)
    if store.exists("btc_funding"):
        fu = store.to_indexed(store.load("btc_funding"))
        fu30 = fu.rolling(30, min_periods=20).mean()
        fu_pct = ind.expanding_pct(fu30, 540)
        df["funding_30d"] = store.as_of(store.make_series(fu30.index, fu30.to_numpy(), dropna=False), cal)
        df["funding_pct"] = store.as_of(store.make_series(fu_pct.index, fu_pct.to_numpy(), dropna=False), cal)
    else:
        df["funding_30d"] = np.nan
        df["funding_pct"] = np.nan

    green = (df["mvrv"] < b["green"]["mvrv_max"]) | (df["ratio_200w"] < b["green"]["ratio_200w_max"])
    red = df["mvrv"] >= b["red"]["mvrv_min"]
    color = pd.Series("orange", index=cal, dtype=object)
    reason = pd.Series("", index=cal, dtype=object)
    color[red.fillna(False)] = "red"
    reason[red.fillna(False)] = f"MVRV ≥ {b['red']['mvrv_min']:g} : les détenteurs ont en moyenne triplé leur mise"
    gm = green.fillna(False)
    color[gm] = "green"
    reason[gm] = np.where((df["mvrv"] < b["green"]["mvrv_max"])[gm], "MVRV < 1 : les détenteurs sont en perte en moyenne",
                          "prix sous sa moyenne des 200 semaines")
    missing = df["mvrv"].isna() | df["ratio_200w"].isna()
    color[missing] = "orange"      # le protocole exclut ces jours ; affichés orange, sans motif trompeur (v1.0.1)
    reason[missing] = "données incomplètes (MVRV ou moyenne 200 semaines indisponible) : pas de jugement"
    df["color"], df["reason"] = color, reason
    df["falling_knife"] = (df["color"] == "green") & df["trend_broken"]
    df["asset"] = "btc"
    return df


# ----------------------------------------------------------------------------------------------
def confirmed_color(color: pd.Series, days: int) -> pd.Series:
    """Une nouvelle couleur n'est affichée/alertée qu'après `days` jours consécutifs (anti-clignotement).
    La règle de couleur elle-même (colonne `color`) n'est pas modifiée."""
    out, cur, run_color, run_len = [], None, None, 0
    for c in color:
        if c == run_color:
            run_len += 1
        else:
            run_color, run_len = c, 1
        if cur is None or (run_color != cur and run_len >= days):
            cur = run_color
        out.append(cur)
    return pd.Series(out, index=color.index)


def compute_all() -> dict[str, pd.DataFrame]:
    r = rules()
    res = {}
    sp = store.to_indexed(store.load("px_sp500"))
    common = {"V": common_valuation(sp.index, sp), "E": common_euphoria(sp.index), "P": common_fear(sp.index)}
    days = int(r.get("confirmation_days", 5))
    for key in r["indices"]["assets"]:
        res[key] = index_signals(key, common={k: v for k, v in common.items()})
    res["btc"] = bitcoin_signals()
    for key, df in res.items():
        df["color_confirmed"] = confirmed_color(df["color"], days)
        log.info("%s : %d jours, dernier %s = %s (brut %s)", key, len(df), df.index[-1].date(), df["color_confirmed"].iloc[-1], df["color"].iloc[-1])
    return res


def _state_run(df: pd.DataFrame) -> dict:
    """Depuis quand l'état confirmé actuel dure, et ce qu'a fait le prix depuis : la rétroaction la plus honnête et la moins chère."""
    col = df["color_confirmed"] if "color_confirmed" in df else df["color"]
    cur = col.iloc[-1]
    changes = col.ne(col.shift())
    start = col.index[changes][-1] if changes.any() else col.index[0]
    px0 = df["price"].loc[start] if "price" in df else np.nan
    perf = float(df["price"].iloc[-1] / px0 - 1) if "price" in df and px0 and not np.isnan(px0) else None
    return {"state_since": str(pd.Timestamp(start).date()), "state_days": int((df.index[-1] - start).days), "perf_since_state": perf,
            "state_color": cur}


def _ref_dates() -> dict:
    """Dates de référence des séries publiées avec retard (affichées à côté des valeurs : la dette sur marge « du jour »
    est celle de fin de mois précédent, l'allocation des ménages celle du trimestre clos il y a 2 à 5 mois)."""
    out = {}
    for name, key in (("margin_debt", "margin_ref_date"), ("aiae", "aiae_ref_date")):
        try:
            s = store.load(name).dropna(subset=["value"])
            out[key] = str(pd.Timestamp(s["ref_date"].max()).date())
            out[key.replace("ref", "available")] = str(pd.Timestamp(s["available_date"].max()).date())
        except Exception:   # série absente : pas bloquant
            pass
    return out


def save_signals(res: dict[str, pd.DataFrame]) -> None:
    latest = {}
    refs = _ref_dates()
    for key, df in res.items():
        df.to_parquet(SIGNALS_DIR / f"{key}.parquet")
        last = df.iloc[-1]
        latest[key] = {k: (None if (isinstance(v, float) and np.isnan(v)) else (v.item() if hasattr(v, "item") else v))
                       for k, v in last.items() if k not in ("asset",)}
        latest[key]["date"] = str(df.index[-1].date())
        latest[key].update(_state_run(df))
        if key != "btc":
            latest[key].update(refs)
            latest[key]["valuation_source"] = "S&P 500 (CAPE de Shiller, comparé à tous les mois depuis 1881)"
            latest[key]["valuation_is_proxy"] = key != "sp500"
    (DOCS_DIR / "latest.json").write_text(json.dumps(latest, indent=1, default=str, ensure_ascii=False), encoding="utf-8")


def load_signals(key: str) -> pd.DataFrame:
    return pd.read_parquet(SIGNALS_DIR / f"{key}.parquet")
