"""Évaluation des candidats de règles v1.0 selon le protocole pré-enregistré (research/v1_protocol.md).

- Hors échantillon : S&P Composite mensuel (Shiller), 1920-1989, rendements réels dividendes inclus, mise en œuvre le mois
  suivant le signal (le prix moyen du mois t n'est connu qu'en fin de mois t).
- Conception : moteur quotidien v0.x (rendements de prix), 1990 → aujourd'hui, S&P 500, Nasdaq-100, MSCI World.
- Bitcoin : 2014 → aujourd'hui.
Rien ici n'ajuste de seuil : les candidats et les critères sont ceux du protocole.
"""
from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from . import indicators as ind
from . import store
from .config import DOCS_DIR, RAW_DIR, ROOT, rules

log = logging.getLogger("feux.longrun")
COLORS = ["green", "orange", "red"]
VARIANTS = ["R1", "R2", "R3"]
VARIANT_NAMES = {"R1": "cher et tendu (V ≥ 80 et X ≥ 90)", "R2": "cher et cassé (V ≥ 80 et tendance cassée)",
                 "R3": "très cher (V ≥ 90)"}
CRIT = {"gap_min": 0.05, "red_share_max": 0.25, "red_episodes_min": 3}
HOLDOUT = ("1920-01-01", "1989-12-31")
DESIGN_START = "1990-01-01"


# ----------------------------------------------------------------------------------------------
# Base mensuelle longue
# ----------------------------------------------------------------------------------------------
def shiller_monthly() -> pd.DataFrame:
    """Colonnes : P (prix moyen nominal), E, CPI, TR (prix réel rendement total, dividendes réinvestis)."""
    raw = pd.read_excel(RAW_DIR / "ie_data.xls", sheet_name="Data", header=None)
    df = raw.iloc[8:, [0, 1, 3, 4, 9]].copy()
    df.columns = ["date", "P", "E", "CPI", "TR"]
    df = df[pd.to_numeric(df["date"], errors="coerce").notna()].copy()
    year = df["date"].astype(float).astype(int)
    month = ((df["date"].astype(float) - year) * 100).round().astype(int)
    month = month.where(month > 0, 10)
    df.index = pd.to_datetime(dict(year=year, month=month, day=1)) + pd.offsets.MonthEnd(0)
    for c in ("P", "E", "CPI", "TR"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.drop(columns="date").sort_index()


def _expanding_pct(s: pd.Series, min_periods: int) -> pd.Series:
    """Percentile de la valeur du jour parmi toutes les valeurs connues jusqu'à elle (incluse)."""
    return ind.pct_against_reference(s, s.dropna(), window=10 ** 7, min_periods=min_periods)


def monthly_frame() -> pd.DataFrame:
    from .loaders import fred

    lag_m = int(rules()["lags"]["shiller_earnings_months"])
    m = shiller_monthly()
    m["cape"] = ind.cape_pit(m["P"], m["E"], m["CPI"], lag_m)
    m["V"] = _expanding_pct(m["cape"], 360)
    sma10 = m["P"].rolling(10, min_periods=10).mean()
    m["T"] = (m["P"] < sma10).where(sma10.notna())
    m["gap10"] = m["P"] / sma10 - 1.0
    m["X"] = _expanding_pct(m["gap10"], 360)
    baa, aaa = fred.fetch("BAA"), fred.fetch("AAA")
    spread = (baa - aaa).dropna()
    spread.index = spread.index + pd.offsets.MonthEnd(0)
    m["spread"] = spread.reindex(m.index)
    m["P_fear"] = _expanding_pct(m["spread"], 120)
    m["drawdown"] = 1.0 - m["TR"] / m["TR"].cummax()
    return m


# ----------------------------------------------------------------------------------------------
# Couleurs des candidats (identiques en mensuel et en quotidien)
# ----------------------------------------------------------------------------------------------
def colorize(V: pd.Series, X: pd.Series, T: pd.Series, P: pd.Series, dd: pd.Series, variant: str) -> pd.Series:
    cap = (dd >= 0.25) & (P >= 80)
    gval = V <= 40
    if variant == "R1":
        red = (V >= 80) & (X >= 90)
    elif variant == "R2":
        red = (V >= 80) & (T == True)  # noqa: E712 — NaN n'est pas « cassé »
    elif variant == "R3":
        red = V >= 90
    else:
        raise ValueError(variant)
    col = pd.Series("orange", index=V.index, dtype=object)
    col[gval.fillna(False)] = "green"
    col[red.fillna(False)] = "red"
    col[cap.fillna(False)] = "green"
    col[V.isna()] = np.nan
    return col


# ----------------------------------------------------------------------------------------------
# Statistiques
# ----------------------------------------------------------------------------------------------
def _ann(x, years):
    return (1.0 + x) ** (1.0 / years) - 1.0


def _episodes(col: pd.Series, min_len: int) -> dict[str, int]:
    c = col.dropna()
    runs = (c != c.shift()).cumsum()
    out = {k: 0 for k in COLORS}
    for _, g in c.groupby(runs):
        if len(g) >= min_len:
            out[g.iloc[0]] += 1
    return out


def stats(level: pd.Series, col: pd.Series, per_year: int, lag: int, start: str, end: str | None = None,
          min_episode: int = 1) -> dict:
    """`level` : indice de richesse (rendement total réel en mensuel, prix en quotidien) ; `lag` : décalage de mise en œuvre."""
    entry = level.shift(-lag)
    win = (col.index >= pd.Timestamp(start)) & ((col.index <= pd.Timestamp(end)) if end else True)
    c = col[win].dropna()
    out = {"début": str(c.index[0].date()), "fin": str(c.index[-1].date()), "n": int(len(c)),
           "part": {k: float((c == k).mean()) for k in COLORS}, "épisodes": _episodes(c, min_episode),
           "changements_par_an": float(((c != c.shift()).sum() - 1) / max((c.index[-1] - c.index[0]).days / 365.25, 1e-9))}
    for label, years in (("1an", 1), ("3ans", 3), ("5ans", 5)):
        n = int(per_year * years)
        fwd = (level.shift(-lag - n) / entry - 1.0).reindex(c.index)
        out[f"rdt_{label}"] = {k: (None if ((c == k) & fwd.notna()).sum() == 0 else float(_ann(fwd[(c == k) & fwd.notna()].median(), years)))
                               for k in COLORS}
        out[f"n_{label}"] = {k: int(((c == k) & fwd.notna()).sum()) for k in COLORS}
    n = int(per_year * 2)
    fut_min = level[::-1].rolling(n, min_periods=n).min()[::-1].shift(-lag - 1)
    dd_next = (1.0 - fut_min / entry).reindex(c.index)
    out["baisse24m_médiane"] = {k: (None if ((c == k) & dd_next.notna()).sum() == 0 else float(dd_next[(c == k) & dd_next.notna()].median())) for k in COLORS}
    out["baisse24m_p90"] = {k: (None if ((c == k) & dd_next.notna()).sum() == 0 else float(dd_next[(c == k) & dd_next.notna()].quantile(0.9))) for k in COLORS}
    g, r = out["rdt_3ans"]["green"], out["rdt_3ans"]["red"]
    out["écart_3ans"] = None if g is None or r is None else float(g - r)
    return out


def check(s: dict) -> dict:
    gap = s["écart_3ans"]
    p90r, p90o = s["baisse24m_p90"]["red"], s["baisse24m_p90"]["orange"]
    res = {"a_écart": gap is not None and gap >= CRIT["gap_min"],
           "b_part_rouge": s["part"]["red"] <= CRIT["red_share_max"],
           "c_épisodes_rouges": s["épisodes"]["red"] >= CRIT["red_episodes_min"],
           "d_queue": p90r is not None and p90o is not None and p90r >= p90o}
    res["tout"] = all(res.values())
    return res


# ----------------------------------------------------------------------------------------------
# Quotidien : composantes v1.0 sur le calendrier de chaque indice
# ----------------------------------------------------------------------------------------------
def daily_components(key: str, cape_m: pd.Series) -> pd.DataFrame:
    df = pd.read_parquet(ROOT / "data" / "signals" / f"{key}.parquet")
    d = pd.DataFrame(index=df.index)
    d["price"] = df["price"]
    ref = cape_m.dropna()
    ref.index = ref.index + pd.Timedelta(days=15)     # CAPE d'un mois connu après l'indice des prix (vers le 15 du mois suivant)
    d["V"] = ind.pct_against_reference(df["cape_live"], ref, window=10 ** 7, min_periods=360)
    d["X"] = _expanding_pct(df["gap_ma200"], 252 * 15)
    d["T"] = df["trend_broken"].astype(float).where(df["trend_broken"].notna())
    d["P"] = df["P"]
    d["drawdown"] = df["drawdown"]
    d["color_v0"] = df["color"]
    return d


# ----------------------------------------------------------------------------------------------
# Bitcoin
# ----------------------------------------------------------------------------------------------
def btc_components() -> pd.DataFrame:
    df = pd.read_parquet(ROOT / "data" / "signals" / "btc.parquet")
    return pd.DataFrame({"price": df["price"], "mvrv": df["mvrv"], "ratio_200w": df["ratio_200w"], "color_v0": df["color"]})


def btc_colorize(d: pd.DataFrame, red_mvrv: float = 3.0) -> pd.Series:
    green = (d["mvrv"] < 1.0) | (d["ratio_200w"] < 1.0)
    red = d["mvrv"] >= red_mvrv
    col = pd.Series("orange", index=d.index, dtype=object)
    col[red.fillna(False)] = "red"
    col[green.fillna(False)] = "green"
    col[d["mvrv"].isna() | d["ratio_200w"].isna()] = np.nan
    return col


# ----------------------------------------------------------------------------------------------
# Exécution du protocole
# ----------------------------------------------------------------------------------------------
def run() -> dict:
    m = monthly_frame()
    out = {"protocole": "research/v1_protocol.md", "critères": CRIT, "hors_échantillon": {}, "conception_mensuelle": {},
           "conception_quotidienne": {}, "bitcoin": {}}
    for v in VARIANTS:
        col = colorize(m["V"], m["X"], m["T"], m["P_fear"], m["drawdown"], v)
        s_ho = stats(m["TR"], col, 12, 1, *HOLDOUT)
        s_dm = stats(m["TR"], col, 12, 1, DESIGN_START)
        out["hors_échantillon"][v] = s_ho | {"critères": check(s_ho)}
        out["conception_mensuelle"][v] = s_dm | {"critères": check(s_dm)}
    cape_m = m["cape"]
    for key in ("sp500", "ndx", "world"):
        d = daily_components(key, cape_m)
        out["conception_quotidienne"][key] = {}
        s0 = stats(d["price"], d["color_v0"], 252, 0, DESIGN_START, min_episode=20)
        out["conception_quotidienne"][key]["v0"] = s0 | {"critères": check(s0)}
        for v in VARIANTS:
            col = colorize(d["V"], d["X"], d["T"], d["P"], d["drawdown"], v)
            s = stats(d["price"], col, 252, 0, DESIGN_START, min_episode=20)
            out["conception_quotidienne"][key][v] = s | {"critères": check(s)}
    # règle de décision (§8)
    passing = [v for v in VARIANTS if out["hors_échantillon"][v]["critères"]["tout"]
               and out["conception_quotidienne"]["sp500"][v]["critères"]["tout"]]
    choice = None
    if passing:
        score = {v: min(out["hors_échantillon"][v]["écart_3ans"], out["conception_quotidienne"]["sp500"][v]["écart_3ans"]) for v in passing}
        best = max(score.values())
        simplicity = ["R3", "R2", "R1"]
        close = [v for v in passing if best - score[v] <= 0.01]
        choice = sorted(close, key=simplicity.index)[0]
    out["retenus"] = passing
    out["choix"] = choice
    # Bitcoin
    b = btc_components()
    for name, thr in (("B1", 3.0), ("B1_sensibilité_3.7", 3.7)):
        col = btc_colorize(b, thr)
        s = stats(b["price"], col, 365, 0, "2014-01-01", min_episode=20)
        crit = {"a_écart": s["écart_3ans"] is not None and s["écart_3ans"] >= 0.05, "b_part_rouge": s["part"]["red"] <= 0.30,
                "c_épisodes_rouges": s["épisodes"]["red"] >= 2}
        crit["tout"] = all(crit.values())
        out["bitcoin"][name] = s | {"critères": crit}
    s0 = stats(b["price"], b["color_v0"], 365, 0, "2014-01-01", min_episode=20)
    out["bitcoin"]["v0"] = s0
    (DOCS_DIR / "longrun_summary.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return out
