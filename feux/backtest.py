"""Validation point-in-time des feux : rendements futurs par couleur, drawdowns, épisodes, coût des
faux positifs sur un plan type, ETF x2 avec/sans filtre de tendance, sensibilité Bitcoin."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import store
from .config import DOCS_DIR, rules
from .signals import load_signals

log = logging.getLogger("feux.backtest")
TD = 252
COLORS = ["green", "orange", "red"]

# Épisodes à reproduire (pré-enregistrés dans le cahier de conception). Tolérance : couleur dominante
# sur les 3 mois (63 jours de bourse) centrés sur la date.
EPISODES = {
    "sp500": [("1999-12-31", {"red", "orange"}, "fin 1999 (attendu rouge ou orange ; rouge via dette sur marge dès mars 2000)"),
              ("2000-03-24", {"red"}, "sommet mars 2000"),
              ("2007-10-09", {"red", "orange"}, "sommet octobre 2007"),
              ("2009-03-09", {"green"}, "creux mars 2009"),
              ("2020-03-23", {"green"}, "creux mars 2020"),
              ("2021-11-30", {"red"}, "fin 2021"),
              ("2022-10-12", {"green"}, "creux octobre 2022")],
    "ndx": [("1999-12-31", {"red"}, "fin 1999"), ("2000-03-24", {"red"}, "sommet mars 2000"),
            ("2007-10-31", {"red", "orange"}, "octobre 2007"), ("2009-03-09", {"green"}, "creux mars 2009"),
            ("2020-03-23", {"green"}, "creux mars 2020"), ("2021-11-30", {"red"}, "fin 2021"),
            ("2022-10-12", {"green"}, "creux octobre 2022")],
    "world": [("2000-03-24", {"red"}, "sommet mars 2000"), ("2007-10-31", {"red", "orange"}, "octobre 2007"),
              ("2009-03-09", {"green"}, "creux mars 2009"), ("2020-03-23", {"green"}, "creux mars 2020"),
              ("2021-11-30", {"red"}, "fin 2021"), ("2022-10-12", {"green"}, "creux octobre 2022")],
    "btc": [("2017-12-17", {"red"}, "sommet décembre 2017"), ("2018-12-15", {"green"}, "creux décembre 2018"),
            ("2020-03-13", {"green"}, "creux mars 2020"), ("2021-04-14", {"red"}, "sommet avril 2021"),
            ("2021-11-10", {"red"}, "sommet novembre 2021"), ("2022-11-21", {"green"}, "creux novembre 2022"),
            ("2025-10-06", {"red"}, "sommet octobre 2025"), ("2026-07-15", {"green"}, "creux juillet 2026")],
}


@dataclass
class AssetResult:
    asset: str
    start: str
    end: str
    share: dict = field(default_factory=dict)
    fwd: pd.DataFrame | None = None
    dd24: pd.DataFrame | None = None
    episodes: list = field(default_factory=list)
    changes_per_year: float = float("nan")
    checks: dict = field(default_factory=dict)


def _ann(x: pd.Series, years: float) -> pd.Series:
    return (1.0 + x) ** (1.0 / years) - 1.0


def forward_stats(df: pd.DataFrame, per_year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    px = df["price"]
    rows, dd_rows = [], []
    for label, years in [("1 an", 1), ("3 ans", 3), ("5 ans", 5)]:
        n = int(per_year * years)
        fwd = px.shift(-n) / px - 1.0
        for c in COLORS:
            m = (df["color"] == c) & fwd.notna()
            if m.sum() == 0:
                continue
            f = fwd[m]
            rows.append({"horizon": label, "couleur": c, "n_jours": int(m.sum()),
                         "médiane_annualisée": _ann(f.median(), years), "moyenne_annualisée": _ann(f.mean(), years),
                         "p10_annualisé": _ann(f.quantile(0.10), years), "part_négative": float((f < 0).mean())})
    # drawdown maximal dans les 24 mois suivants
    n = int(per_year * 2)
    fwd_min = px[::-1].rolling(n, min_periods=n).min()[::-1].shift(-1)  # min des n jours suivants
    dd_next = 1.0 - fwd_min / px
    for c in COLORS:
        m = (df["color"] == c) & dd_next.notna()
        if m.sum() == 0:
            continue
        d = dd_next[m]
        dd_rows.append({"couleur": c, "n_jours": int(m.sum()), "drawdown_24m_médian": d.median(),
                        "drawdown_24m_p90": d.quantile(0.90), "part_drawdown_>20%": float((d > 0.20).mean())})
    return pd.DataFrame(rows), pd.DataFrame(dd_rows)


def episode_check(df: pd.DataFrame, asset: str, window: int = 31) -> list[dict]:
    out = []
    for date, expected, label in EPISODES.get(asset, []):
        d = pd.Timestamp(date)
        if d < df.index[0] or d > df.index[-1]:
            out.append({"date": date, "épisode": label, "attendu": "/".join(sorted(expected)), "obtenu": "hors échantillon", "ok": None})
            continue
        i = df.index.searchsorted(d)
        exact = df["color"].iloc[min(i, len(df) - 1)]
        around = df["color"].iloc[max(0, i - window): i + window]
        dominant = around.value_counts().idxmax()
        ok = (exact in expected) or (dominant in expected)
        out.append({"date": date, "épisode": label, "attendu": "/".join(sorted(expected)), "obtenu": exact,
                    "dominant_±3_mois": dominant, "ok": bool(ok)})
    return out


def evaluate(asset: str, df: pd.DataFrame, start: str, per_year: int) -> AssetResult:
    r = rules()["acceptance"]
    d = df[df.index >= start].copy()
    d = d[d["color"].notna()]
    res = AssetResult(asset=asset, start=str(d.index[0].date()), end=str(d.index[-1].date()))
    res.share = d["color"].value_counts(normalize=True).reindex(COLORS).fillna(0).round(4).to_dict()
    res.fwd, res.dd24 = forward_stats(d, per_year)
    res.episodes = episode_check(d, asset)
    changes = (d["color"] != d["color"].shift()).sum() - 1
    res.changes_per_year = float(changes / ((d.index[-1] - d.index[0]).days / 365.25))
    # critères
    f3 = res.fwd[res.fwd["horizon"] == "3 ans"].set_index("couleur")["médiane_annualisée"]
    gap = float(f3.get("green", np.nan) - f3.get("red", np.nan))
    dd = res.dd24.set_index("couleur")["drawdown_24m_médian"]
    red_cap = r["red_time_share_max_btc"] if asset == "btc" else r["red_time_share_max_indices"]
    eps = [e for e in res.episodes if e["ok"] is not None]
    res.checks = {
        "part_rouge": {"valeur": res.share["red"], "seuil": red_cap, "ok": res.share["red"] <= red_cap},
        "écart_3ans_vert_moins_rouge": {"valeur": gap, "seuil": r["fwd3y_median_gap_min_annual"],
                                        "ok": bool(gap >= r["fwd3y_median_gap_min_annual"]) if gap == gap else None},
        "drawdown24m_rouge_plus_profond": {"rouge": float(dd.get("red", np.nan)), "vert": float(dd.get("green", np.nan)),
                                           "ok": bool(dd.get("red", np.nan) > dd.get("green", np.nan)) if dd.notna().all() else None},
        "épisodes_ok": {"valeur": sum(1 for e in eps if e["ok"]), "total": len(eps)},
        "changements_par_an": res.changes_per_year,
    }
    return res


# ----------------------------------------------------------------------------------------------
# Plan type : versement mensuel + montant exceptionnel annuel, déployé selon la couleur
# ----------------------------------------------------------------------------------------------
def plan_simulation(df: pd.DataFrame, start: str = "1990-01-01") -> dict:
    """Compare : (A) exceptionnel investi chaque janvier sans regarder le feu ; (B) exceptionnel mis en
    réserve (rémunérée au taux des bons du Trésor 3 mois) et déployé par tiers mensuels uniquement en vert
    (par sixièmes si « couteau qui tombe ») ; (C) réserve déployée par tiers dès que le feu n'est PAS rouge.
    Les versements mensuels sont identiques dans les trois cas.
    Prix seuls (hors dividendes) : identiques pour A et B, donc sans effet sur la comparaison."""
    p = rules()["acceptance"]["plan_type"]
    monthly, yearly = float(p["monthly_eur"]), float(p["exceptional_yearly_eur"])
    d = df[df.index >= start]
    m = d["price"].resample("ME").last().dropna()
    color_m = d["color"].resample("ME").last().reindex(m.index).ffill()
    knife_m = d["falling_knife"].resample("ME").last().reindex(m.index).fillna(False)
    tb = store.to_indexed(store.load("tbill3m")).reindex(m.index, method="ffill").fillna(0) / 100.0
    units_a = units_b = units_c = 0.0
    reserve_b = reserve_c = 0.0
    invested = 0.0
    hist = []
    for i, (date, px) in enumerate(m.items()):
        units_a += monthly / px
        units_b += monthly / px
        units_c += monthly / px
        invested += monthly
        if date.month == 1:
            units_a += yearly / px
            reserve_b += yearly
            reserve_c += yearly
            invested += yearly
        growth = (1 + tb.loc[date]) ** (1 / 12)
        reserve_b *= growth
        reserve_c *= growth
        col = color_m.loc[date]
        if col == "green" and reserve_b > 0:
            frac = 1 / 6 if knife_m.loc[date] else 1 / 3
            amt = min(reserve_b, max(reserve_b * frac, yearly / 6))
            units_b += amt / px
            reserve_b -= amt
        if col != "red" and reserve_c > 0:   # variante C : on ne diffère qu'en rouge
            amt = min(reserve_c, max(reserve_c / 3, yearly / 6))
            units_c += amt / px
            reserve_c -= amt
        hist.append((date, units_a * px, units_b * px + reserve_b, reserve_b, units_c * px + reserve_c, reserve_c, invested))
    h = pd.DataFrame(hist, columns=["date", "A", "B", "réserve_B", "C", "réserve_C", "investi"]).set_index("date")
    return {
        "période": f"{h.index[0].date()} → {h.index[-1].date()}",
        "investi_total": float(h["investi"].iloc[-1]),
        "A_valeur_finale": float(h["A"].iloc[-1]),
        "B_valeur_finale": float(h["B"].iloc[-1]),
        "B_moins_A": float(h["B"].iloc[-1] - h["A"].iloc[-1]),
        "B_moins_A_pct": float(h["B"].iloc[-1] / h["A"].iloc[-1] - 1),
        "C_valeur_finale": float(h["C"].iloc[-1]),
        "C_moins_A": float(h["C"].iloc[-1] - h["A"].iloc[-1]),
        "C_moins_A_pct": float(h["C"].iloc[-1] / h["A"].iloc[-1] - 1),
        "C_drawdown_max": float((1 - h["C"] / h["C"].cummax()).max()),
        "réserve_B_finale": float(h["réserve_B"].iloc[-1]),
        "réserve_B_max": float(h["réserve_B"].max()),
        "A_drawdown_max": float((1 - h["A"] / h["A"].cummax()).max()),
        "B_drawdown_max": float((1 - h["B"] / h["B"].cummax()).max()),
        "série": h,
    }


# ----------------------------------------------------------------------------------------------
# ETF x2 quotidien synthétique sur le Nasdaq-100
# ----------------------------------------------------------------------------------------------
def leveraged_simulation(df: pd.DataFrame, start: str = "1985-10-01", fee: float = 0.006, spread: float = 0.005) -> dict:
    px = df.loc[df.index >= start, "price"]
    r1 = px.pct_change().fillna(0.0)
    tb = store.to_indexed(store.load("tbill3m")).reindex(px.index, method="ffill").bfill() / 100.0
    daily_cost = (tb + spread) / TD + fee / TD          # financement de la part empruntée + frais
    r2 = 2 * r1 - daily_cost
    trend_ok = ~df.loc[px.index, "trend_broken"].astype(bool)   # drapeau connu en fin de mois précédent
    r_filtered = np.where(trend_ok, r2, r1)
    out = {}
    for name, rr in [("Nasdaq-100 sans levier", r1), ("x2 permanent", r2), ("x2 seulement si tendance OK (MM10 mois)", pd.Series(r_filtered, index=px.index))]:
        w = (1 + rr).cumprod()
        years = (px.index[-1] - px.index[0]).days / 365.25
        out[name] = {"multiple": float(w.iloc[-1]), "cagr": float(w.iloc[-1] ** (1 / years) - 1),
                     "drawdown_max": float((1 - w / w.cummax()).max()),
                     "pire_année": float((1 + rr).groupby(px.index.year).prod().min() - 1)}
        if name.startswith("x2 perm"):
            w2 = w
        # drawdown 2000-2002
        sub = w[(w.index >= "2000-03-01") & (w.index <= "2002-12-31")]
        out[name]["drawdown_2000_2002"] = float(1 - sub.min() / sub.iloc[0]) if len(sub) else float("nan")
    out["_part_du_temps_tendance_ok"] = float(trend_ok.mean())
    return out


# ----------------------------------------------------------------------------------------------
# Sensibilité Bitcoin : seuil rouge 1,5σ (gelé) contre 1,0σ (ajustement candidat), avec hold-out déc. 2013
# ----------------------------------------------------------------------------------------------
def btc_sensitivity(df: pd.DataFrame) -> dict:
    b = rules()["bitcoin"]
    out = {}
    for z in [b["valuation"]["red_min_z"], 1.0]:
        red = (df["V"] >= z) & df["gsy"]
        green_cap = (df["drawdown"] >= b["capitulation"]["drawdown_min"]) & (df["fng_30d"] <= b["capitulation"]["fng_30d_max"])
        green_val = df["V"] <= b["valuation"]["green_max_z"]
        color = pd.Series("orange", index=df.index, dtype=object)
        color[green_val] = "green"; color[red] = "red"; color[green_cap] = "green"
        color[df["V"].isna() & ~green_cap] = "orange"
        d = df.assign(color=color)
        d = d[d.index >= "2013-07-01"]
        fwd, dd = forward_stats(d, 365)
        peaks = {}
        for date in ["2013-12-04", "2017-12-17", "2021-04-14", "2021-11-10", "2025-10-06"]:
            i = d.index.searchsorted(pd.Timestamp(date))
            peaks[date] = d["color"].iloc[min(i, len(d) - 1)]
        out[f"seuil_{z}"] = {"part_rouge": float((d["color"] == "red").mean()), "sommets": peaks,
                             "fwd": fwd, "dd24": dd}
    return out


# ----------------------------------------------------------------------------------------------
def _fmt_pct(x) -> str:
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:+.1f} %"


def _table(df: pd.DataFrame, pct_cols: list[str]) -> str:
    d = df.copy()
    for c in pct_cols:
        if c in d:
            d[c] = d[c].map(_fmt_pct)
    return d.to_html(index=False, border=0, classes="t", float_format=lambda v: f"{v:,.2f}")


def run_all() -> dict:
    r = rules()
    summary, html = {}, []
    html.append("<h1>Validation point-in-time des feux</h1>")
    html.append(f"<p>Règles gelées le {r['frozen_at']} (version {r['version']}). Rendements de prix (hors dividendes) ; "
                "un jour est classé par sa couleur du jour, les rendements sont ceux des 1, 3 et 5 années suivantes.</p>")
    results = {}
    for asset in list(r["indices"]["assets"]) + ["btc"]:
        df = load_signals(asset)
        start = "1990-01-01" if asset != "btc" else "2014-01-01"
        res = evaluate(asset, df, start, TD if asset != "btc" else 365)
        results[asset] = res
        name = r["indices"]["assets"].get(asset, {}).get("name", "Bitcoin")
        html.append(f"<h2>{name} ({res.start} → {res.end})</h2>")
        html.append("<p>Part du temps : " + ", ".join(f"<b class='{c}'>{c}</b> {100 * res.share[c]:.0f} %" for c in COLORS)
                    + f" ; changements de couleur : {res.changes_per_year:.1f} par an.</p>")
        html.append(_table(res.fwd, ["médiane_annualisée", "moyenne_annualisée", "p10_annualisé", "part_négative"]))
        html.append(_table(res.dd24, ["drawdown_24m_médian", "drawdown_24m_p90", "part_drawdown_>20%"]))
        html.append(_table(pd.DataFrame(res.episodes), []))
        html.append("<pre>" + json.dumps(res.checks, indent=1, ensure_ascii=False, default=str) + "</pre>")
        summary[asset] = {"share": res.share, "checks": res.checks, "episodes": res.episodes,
                          "fwd": res.fwd.to_dict(orient="records"), "dd24": res.dd24.to_dict(orient="records")}
        log.info("%s : rouge %.0f %% | vert %.0f %% | épisodes %s/%s | écart 3 ans vert−rouge %s", asset, 100 * res.share["red"],
                 100 * res.share["green"], res.checks["épisodes_ok"]["valeur"], res.checks["épisodes_ok"]["total"],
                 _fmt_pct(res.checks["écart_3ans_vert_moins_rouge"]["valeur"]))

    # plan type
    html.append("<h2>Coût des faux positifs : plan type (1 000 €/mois + 10 000 €/an exceptionnels)</h2>")
    for asset in r["indices"]["assets"]:
        sim = plan_simulation(load_signals(asset))
        summary[f"plan_{asset}"] = {k: v for k, v in sim.items() if k != "série"}
        html.append(f"<p><b>{r['indices']['assets'][asset]['name']}</b> ({sim['période']}) : investi {sim['investi_total']:,.0f} € ; "
                    f"A (exceptionnel investi chaque janvier) = {sim['A_valeur_finale']:,.0f} € ; "
                    f"B (réserve déployée en vert) = {sim['B_valeur_finale']:,.0f} € ; B − A = {sim['B_moins_A']:,.0f} € "
                    f"({_fmt_pct(sim['B_moins_A_pct'])}) ; C (différé seulement en rouge) = {sim['C_valeur_finale']:,.0f} € ; C − A = {sim['C_moins_A']:,.0f} € "
                    f"({_fmt_pct(sim['C_moins_A_pct'])}) ; réserve B finale non déployée {sim['réserve_B_finale']:,.0f} € "
                    f"(max {sim['réserve_B_max']:,.0f} €) ; drawdown max A {_fmt_pct(sim['A_drawdown_max'])}, B {_fmt_pct(sim['B_drawdown_max'])}, C {_fmt_pct(sim['C_drawdown_max'])}.</p>")
        log.info("plan %s : B−A = %.0f € (%s) | C−A = %.0f € (%s) | réserve B finale %.0f €", asset, sim["B_moins_A"], _fmt_pct(sim["B_moins_A_pct"]),
                 sim["C_moins_A"], _fmt_pct(sim["C_moins_A_pct"]), sim["réserve_B_finale"])

    # levier
    lev = leveraged_simulation(load_signals("ndx"))
    summary["levier_ndx"] = lev
    html.append("<h2>ETF Nasdaq-100 x2 quotidien (synthétique : 2× rendement − financement − 0,6 % de frais), depuis octobre 1985</h2>")
    rows = [{"stratégie": k, **v} for k, v in lev.items() if not k.startswith("_")]
    html.append(_table(pd.DataFrame(rows), ["cagr", "drawdown_max", "pire_année", "drawdown_2000_2002"]))
    html.append(f"<p>Part du temps avec tendance OK : {100 * lev['_part_du_temps_tendance_ok']:.0f} %.</p>")
    for k, v in lev.items():
        if not k.startswith("_"):
            log.info("levier %s : multiple %.1f, CAGR %s, DD max %s, DD 2000-02 %s", k, v["multiple"], _fmt_pct(v["cagr"]),
                     _fmt_pct(v["drawdown_max"]), _fmt_pct(v["drawdown_2000_2002"]))

    # sensibilité BTC
    sens = btc_sensitivity(load_signals("btc"))
    html.append("<h2>Bitcoin : sensibilité du seuil rouge (1,5σ gelé contre 1,0σ candidat ; déc. 2013 = période non utilisée)</h2>")
    for k, v in sens.items():
        html.append(f"<h3>{k}</h3><p>part rouge {100 * v['part_rouge']:.0f} % ; sommets : {v['sommets']}</p>")
        html.append(_table(v["fwd"], ["médiane_annualisée", "moyenne_annualisée", "p10_annualisé", "part_négative"]))
        summary[f"btc_{k}"] = {"part_rouge": v["part_rouge"], "sommets": v["sommets"], "fwd": v["fwd"].to_dict(orient="records")}
        log.info("btc %s : rouge %.0f %%, sommets %s", k, 100 * v["part_rouge"], v["sommets"])

    page = ("<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>Validation des feux</title>"
            "<style>body{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#222}"
            ".t{border-collapse:collapse;margin:1rem 0;font-size:14px}.t td,.t th{border-bottom:1px solid #ddd;padding:4px 8px;text-align:right}"
            ".t th{background:#f5f5f5}.t td:first-child,.t th:first-child{text-align:left}"
            "b.green{color:#1a7f37}b.orange{color:#b35c00}b.red{color:#b3261e}pre{background:#f7f7f7;padding:8px;font-size:12px}</style></head><body>"
            + "\n".join(html) + "</body></html>")
    (DOCS_DIR / "backtest.html").write_text(page, encoding="utf-8")
    (DOCS_DIR / "backtest_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    log.info("Rapport : %s", DOCS_DIR / "backtest.html")
    return summary
