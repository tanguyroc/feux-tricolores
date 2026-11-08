"""Robustesse : stabilité par sous-période, intervalles de confiance par bootstrap de blocs, sensibilité
aux seuils (un paramètre à la fois, sans retouche des règles), règle de confirmation, observation 1985-1989."""
from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from .config import DOCS_DIR, rules
from .signals import confirmed_color, load_signals

log = logging.getLogger("feux.robustness")
TD = 252
COLORS = ["green", "orange", "red"]


def _fwd(df: pd.DataFrame, years: int, per_year: int) -> pd.Series:
    n = per_year * years
    return (df["price"].shift(-n) / df["price"]) ** (1.0 / years) - 1.0


def _dd24(df: pd.DataFrame, per_year: int) -> pd.Series:
    n = per_year * 2
    fwd_min = df["price"][::-1].rolling(n, min_periods=n).min()[::-1].shift(-1)
    return 1.0 - fwd_min / df["price"]


def median_by_color(df: pd.DataFrame, fwd: pd.Series) -> dict:
    out = {}
    for c in COLORS:
        m = (df["color"] == c) & fwd.notna()
        out[c] = float(fwd[m].median()) if m.sum() > 0 else float("nan")
        out[f"n_{c}"] = int(m.sum())
    return out


# ----------------------------------------------------------------------------------------------
def subperiods(df: pd.DataFrame, per_year: int, cuts: list[tuple[str, str, str]]) -> pd.DataFrame:
    fwd3 = _fwd(df, 3, per_year)
    dd = _dd24(df, per_year)
    rows = []
    for label, a, b in cuts:
        d = df[(df.index >= a) & (df.index <= b)]
        f = fwd3.reindex(d.index)
        x = dd.reindex(d.index)
        row = {"période": label, "jours": len(d)}
        for c in COLORS:
            m = (d["color"] == c)
            row[f"part_{c}"] = float(m.mean())
            row[f"3a_{c}"] = float(f[m & f.notna()].median()) if (m & f.notna()).sum() else np.nan
            row[f"dd24_{c}"] = float(x[m & x.notna()].median()) if (m & x.notna()).sum() else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------------------------
def block_bootstrap_gap(df: pd.DataFrame, per_year: int, block: int = 252, reps: int = 1000, seed: int = 7) -> dict:
    """IC à 90 % de l'écart (médiane vert − médiane rouge) du rendement annualisé à 3 ans,
    par bootstrap de blocs circulaires sur les jours (blocs d'un an : les fenêtres se chevauchent)."""
    fwd3 = _fwd(df, 3, per_year)
    ok = fwd3.notna() & df["color"].isin(["green", "red"])
    colors = df["color"][ok].to_numpy()
    vals = fwd3[ok].to_numpy()
    n = len(vals)
    if n < 2 * block:
        return {"n": n, "note": "échantillon trop court"}
    rng = np.random.default_rng(seed)
    gaps = []
    nblocks = int(np.ceil(n / block))
    for _ in range(reps):
        starts = rng.integers(0, n, size=nblocks)
        idx = np.concatenate([(s + np.arange(block)) % n for s in starts])[:n]
        c, v = colors[idx], vals[idx]
        g, r = v[c == "green"], v[c == "red"]
        if len(g) < 30 or len(r) < 30:
            continue
        gaps.append(np.median(g) - np.median(r))
    gaps = np.array(gaps)
    point = float(np.median(vals[colors == "green"]) - np.median(vals[colors == "red"]))
    return {"n": int(n), "écart_point": point, "ic90_bas": float(np.percentile(gaps, 5)), "ic90_haut": float(np.percentile(gaps, 95)),
            "part_répliques_écart_négatif": float((gaps <= 0).mean()), "répliques": int(len(gaps))}


# ----------------------------------------------------------------------------------------------
def sensitivity(df: pd.DataFrame, per_year: int) -> pd.DataFrame:
    """Un seuil à la fois autour des valeurs gelées ; les familles V/X/E/P ne sont pas recalculées."""
    base = rules()["indices"]
    fwd3 = _fwd(df, 3, per_year)
    dd = _dd24(df, per_year)
    variants = [("règles gelées", {})]
    for v in (75, 85):
        variants.append((f"V rouge ≥ {v}", {("valuation", "red_min"): v}))
    for x in (85, 95):
        variants.append((f"X rouge ≥ {x}", {("extension", "red_min"): x}))
    for e in (75, 85):
        variants.append((f"E rouge ≥ {e}", {("euphoria", "red_min"): e}))
    for g in (35, 45):
        variants.append((f"V vert ≤ {g}", {("valuation", "green_max"): g}))
    for d in (0.20, 0.30):
        variants.append((f"capitulation : baisse ≥ {int(100 * d)} %", {("fear", "drawdown_min"): d}))
    for p in (75, 85):
        variants.append((f"capitulation : peur ≥ {p}", {("fear", "green_min"): p}))
    variants.append(("sans critère GSY", {"no_gsy": True}))
    rows = []
    for label, over in variants:
        r = json.loads(json.dumps(base))
        d = df.copy()
        for k, val in over.items():
            if k == "no_gsy":
                d["gsy"] = False
            else:
                r[k[0]][k[1]] = val
        d = _colorize_with(d, r)
        row = {"variante": label}
        for c in COLORS:
            m = d["color"] == c
            row[f"part_{c}"] = float(m.mean())
            row[f"3a_{c}"] = float(fwd3[m & fwd3.notna()].median()) if (m & fwd3.notna()).sum() else np.nan
        row["dd24_rouge"] = float(dd[(d["color"] == "red") & dd.notna()].median()) if ((d["color"] == "red") & dd.notna()).sum() else np.nan
        row["écart_3a_vert_rouge"] = row["3a_green"] - row["3a_red"]
        rows.append(row)
    return pd.DataFrame(rows)


def _colorize_with(df: pd.DataFrame, r: dict) -> pd.DataFrame:
    V, X, E, P = df["V"], df["X"], df["E"], df["P"]
    red = (V >= r["valuation"]["red_min"]) & ((X >= r["extension"]["red_min"]) | (E >= r["euphoria"]["red_min"]) | df["gsy"])
    green_cap = (df["drawdown"] >= r["fear"]["drawdown_min"]) & (P >= r["fear"]["green_min"])
    green_val = V <= r["valuation"]["green_max"]
    color = pd.Series("orange", index=df.index, dtype=object)
    color[green_val] = "green"
    color[red] = "red"
    color[green_cap] = "green"
    color[V.isna() & ~green_cap] = "orange"
    df = df.copy()
    df["color"] = color
    return df


# ----------------------------------------------------------------------------------------------
def confirmation_effect(df: pd.DataFrame, per_year: int, days: int = 5) -> dict:
    fwd3 = _fwd(df, 3, per_year)
    years = (df.index[-1] - df.index[0]).days / 365.25
    raw = df["color"]
    conf = confirmed_color(raw, days)
    out = {"jours_confirmation": days,
           "changements_par_an_brut": float(((raw != raw.shift()).sum() - 1) / years),
           "changements_par_an_confirmé": float(((conf != conf.shift()).sum() - 1) / years)}
    for name, col in (("brut", raw), ("confirmé", conf)):
        d = df.assign(color=col)
        out[f"3a_{name}"] = {c: median_by_color(d, fwd3)[c] for c in COLORS}
        out[f"part_rouge_{name}"] = float((col == "red").mean())
    return out


# ----------------------------------------------------------------------------------------------
def _fmt(x, pct=True):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return f"{100 * x:+.1f} %" if pct else f"{x:.2f}"


def _html_table(df: pd.DataFrame, pct_prefixes=("part_", "3a_", "dd24_", "écart")) -> str:
    d = df.copy()
    for c in d.columns:
        if any(c.startswith(p) for p in pct_prefixes) and d[c].dtype != object:
            d[c] = d[c].map(lambda v: _fmt(v) if c.startswith(("3a_", "écart")) else ("–" if pd.isna(v) else f"{100 * v:.0f} %"))
    return d.to_html(index=False, border=0, classes="t")


def run_all() -> dict:
    r = rules()
    html, summary = [], {}
    html.append("<h1>Robustesse des feux</h1><p>Toutes les analyses utilisent les couleurs point-in-time déjà calculées. "
                "Aucun seuil n'a été modifié à la suite de ces résultats (voir CHANGELOG.md).</p>")
    names = {**{k: v["name"] for k, v in r["indices"]["assets"].items()}, "btc": "Bitcoin"}
    for asset, name in names.items():
        df = load_signals(asset)
        per_year = TD if asset != "btc" else 365
        start = "1985-01-01" if asset != "btc" else "2014-01-01"
        df = df[df.index >= start]
        html.append(f"<h2>{name}</h2>")
        # sous-périodes
        if asset == "btc":
            cuts = [("2014-2020", "2014-01-01", "2020-12-31"), ("2021-2026", "2021-01-01", "2026-12-31"), ("ensemble", "2014-01-01", "2026-12-31")]
        else:
            cuts = [("1985-1999", "1985-01-01", "1999-12-31"), ("2000-2012", "2000-01-01", "2012-12-31"), ("2013-2026", "2013-01-01", "2026-12-31"),
                    ("ensemble 1985-2026", "1985-01-01", "2026-12-31")]
        sp = subperiods(df, per_year, cuts)
        html.append("<h3>Stabilité par sous-période (rendement médian annualisé à 3 ans ; baisse médiane à 24 mois)</h3>" + _html_table(sp))
        # bootstrap
        bb = block_bootstrap_gap(df, per_year)
        html.append("<h3>Écart vert − rouge (3 ans, annualisé) : bootstrap de blocs d'un an, 1 000 répliques</h3>"
                    + (f"<p>Écart observé {_fmt(bb['écart_point'])} ; IC 90 % [{_fmt(bb['ic90_bas'])} ; {_fmt(bb['ic90_haut'])}] ; "
                       f"part des répliques où l'écart est ≤ 0 : {100 * bb['part_répliques_écart_négatif']:.0f} % (n = {bb['n']} jours).</p>"
                       if "écart_point" in bb else f"<p>{bb.get('note')}</p>"))
        # confirmation
        ce = confirmation_effect(df, per_year)
        html.append("<h3>Règle de confirmation (5 jours consécutifs avant d'afficher une nouvelle couleur)</h3>"
                    f"<p>Changements par an : {ce['changements_par_an_brut']:.1f} (brut) → {ce['changements_par_an_confirmé']:.1f} (confirmé). "
                    f"Part en rouge : {100 * ce['part_rouge_brut']:.0f} % → {100 * ce['part_rouge_confirmé']:.0f} %. "
                    "Rendement médian à 3 ans par couleur : brut "
                    + ", ".join(f"{c} {_fmt(ce['3a_brut'][c])}" for c in COLORS) + " ; confirmé "
                    + ", ".join(f"{c} {_fmt(ce['3a_confirmé'][c])}" for c in COLORS) + ".</p>")
        entry = {"sous_périodes": sp.to_dict(orient="records"), "bootstrap": bb, "confirmation": ce}
        # sensibilité (indices seulement : les familles V/X/E/P n'existent pas pour le Bitcoin)
        if asset != "btc":
            se = sensitivity(df, per_year)
            html.append("<h3>Sensibilité aux seuils (un paramètre à la fois)</h3>" + _html_table(se))
            entry["sensibilité"] = se.to_dict(orient="records")
            # 1985-1989 : hors conception
            d8 = df[(df.index >= "1985-01-01") & (df.index <= "1989-12-31")]
            shares = d8.groupby(d8.index.year)["color"].value_counts(normalize=True).unstack().fillna(0)
            around = df.loc["1987-06-01":"1988-03-31", "color"].resample("ME").agg(lambda s: s.value_counts().idxmax())
            html.append("<h3>Observation hors conception : 1985-1989 (non utilisée pour fixer les règles)</h3>"
                        + shares.map(lambda v: f"{100 * v:.0f} %").to_html(border=0, classes="t")
                        + "<p>Couleur dominante par mois, juin 1987 → mars 1988 : "
                        + ", ".join(f"{d:%m/%Y} {c}" for d, c in around.items()) + ".</p>")
            entry["1985_1989"] = shares.round(3).to_dict()
            entry["1987"] = {f"{d:%Y-%m}": c for d, c in around.items()}
        summary[asset] = entry
        log.info("%s : IC90 écart 3 ans [%s ; %s], changements/an %.1f → %.1f avec confirmation", name,
                 _fmt(bb.get("ic90_bas")), _fmt(bb.get("ic90_haut")), ce["changements_par_an_brut"], ce["changements_par_an_confirmé"])

    page = ("<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>Robustesse des feux</title>"
            "<style>body{font-family:system-ui,sans-serif;max-width:1150px;margin:2rem auto;padding:0 1rem;color:#222}"
            ".t{border-collapse:collapse;margin:1rem 0;font-size:13px}.t td,.t th{border-bottom:1px solid #ddd;padding:4px 8px;text-align:right}"
            ".t th{background:#f5f5f5}.t td:first-child,.t th:first-child{text-align:left}h3{margin-top:1.5rem;font-size:15px}</style></head><body>"
            + "\n".join(html) + "</body></html>")
    (DOCS_DIR / "robustness.html").write_text(page, encoding="utf-8")
    (DOCS_DIR / "fragments").mkdir(exist_ok=True)
    (DOCS_DIR / "fragments" / "robustness.html").write_text("\n".join(html), encoding="utf-8")
    (DOCS_DIR / "robustness_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    log.info("Rapport : %s", DOCS_DIR / "robustness.html")
    return summary
