"""Tableau de bord statique (docs/index.html), autonome, sans dépendance externe."""
from __future__ import annotations

import datetime as dt
import html
import json
import logging

import pandas as pd

from .config import DOCS_DIR, rules
from .explain import conduct_text, explain_btc, explain_index
from .signals import load_signals

log = logging.getLogger("feux.dashboard")

CSS = """
:root{--green:#1a7f37;--orange:#c7641a;--red:#b3261e;--bg:#fafaf8;--card:#fff;--ink:#1f2328;--muted:#656d76;--line:#e6e8eb}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 20px 60px}h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:36px 0 12px}
.sub{color:var(--muted);margin:0 0 20px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 18px 14px;display:flex;flex-direction:column;gap:8px}
.head{display:flex;align-items:center;gap:12px}.dot{width:26px;height:26px;border-radius:50%;flex:none;box-shadow:inset 0 0 0 3px rgba(255,255,255,.6)}
.dot.green{background:var(--green)}.dot.orange{background:var(--orange)}.dot.red{background:var(--red)}
.name{font-weight:650;font-size:17px}.state{font-weight:700;letter-spacing:.04em}.state.green{color:var(--green)}.state.orange{color:var(--orange)}.state.red{color:var(--red)}
.since{color:var(--muted);font-size:13px}.reason{font-size:14px}.kv{display:grid;grid-template-columns:1fr auto;gap:2px 10px;font-size:13px;margin-top:4px}
.kv span:nth-child(even){text-align:right;font-variant-numeric:tabular-nums}.kv .lbl{color:var(--muted)}
.flag{display:inline-block;font-size:12px;padding:2px 8px;border-radius:999px;border:1px solid var(--line);color:var(--muted);margin-right:6px}
.flag.on{border-color:var(--red);color:var(--red);font-weight:600}
.timeline{width:100%;height:26px;display:block;border-radius:6px;overflow:hidden;border:1px solid var(--line)}
.legend{font-size:12px;color:var(--muted);display:flex;gap:14px;flex-wrap:wrap}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid var(--line);padding:7px 8px;text-align:left;vertical-align:top}th{background:#f3f4f6}
td.c{text-align:center;font-weight:700}.c.green{color:var(--green)}.c.orange{color:var(--orange)}.c.red{color:var(--red)}
details{margin:8px 0}summary{cursor:pointer;color:var(--muted)}.expl{font-size:14px;background:#f6f7f9;border-radius:8px;padding:10px 12px}
footer{color:var(--muted);font-size:12px;margin-top:40px;border-top:1px solid var(--line);padding-top:12px}
a{color:#0b57d0}.warn{background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:10px 12px;font-size:14px}
"""

LABEL = {"green": "VERT", "orange": "ORANGE", "red": "ROUGE"}
HEX = {"green": "#1a7f37", "orange": "#c7641a", "red": "#b3261e"}


def _since(df: pd.DataFrame) -> str:
    col = df["color"]
    last = col.iloc[-1]
    changes = col[col != last]
    start = col.index[0] if changes.empty else col.index[col.index.get_loc(changes.index[-1]) + 1]
    return start.strftime("%d/%m/%Y")


def _timeline_svg(df: pd.DataFrame, start: str) -> str:
    d = df[df.index >= start]["color"].resample("ME").last().dropna()
    n = len(d)
    if n == 0:
        return ""
    rects = []
    for i, (date, c) in enumerate(d.items()):
        rects.append(f"<rect x='{1000 * i / n:.2f}' y='0' width='{1000 / n + 0.3:.2f}' height='24' fill='{HEX[c]}'><title>{date:%m/%Y} : {LABEL[c]}</title></rect>")
    return (f"<svg class='timeline' viewBox='0 0 1000 24' preserveAspectRatio='none' xmlns='http://www.w3.org/2000/svg'>"
            + "".join(rects) + "</svg>"
            + f"<div class='legend' style='justify-content:space-between'><span>{d.index[0]:%Y}</span><span>{d.index[-1]:%m/%Y}</span></div>")


def _fmt(x, fmt="{:.0f}", suffix="", scale=1.0):
    try:
        if x is None or pd.isna(x):
            return "n.d."
        return fmt.format(scale * x) + suffix
    except Exception:  # noqa: BLE001
        return "n.d."


def _card_index(key: str, name: str, df: pd.DataFrame) -> str:
    row = df.iloc[-1]
    c = row["color"]
    kv = [
        ("Valorisation V", _fmt(row["V"])), ("— CAPE (vivant)", _fmt(row["cape_live"], "{:.1f}") + f" · p{_fmt(row['cape_pct'])}"),
        ("— Excess CAPE Yield", _fmt(row["ecy_live"], "{:.2f}", " %", 100)), ("— Allocation actions (AIAE)", _fmt(row["aiae"], "{:.1f}", " %", 100) + f" · p{_fmt(row['aiae_pct'])}"),
        ("Extension X", _fmt(row["X"])), ("— écart MM200 j", _fmt(row["gap_ma200"], "{:+.1f}", " %", 100)), ("— perf. 12 mois", _fmt(row["mom_12m"], "{:+.1f}", " %", 100)),
        ("Euphorie E (dette sur marge)", _fmt(row["E"]) + f" · {_fmt(row['margin_yoy'], '{:+.0f}', ' %/an', 100)}"),
        ("Peur P", _fmt(row["P"]) + f" · VIX {_fmt(row['vix'], '{:.1f}')}"), ("Baisse depuis le plus haut", _fmt(row["drawdown"], "{:.1f}", " %", 100)),
        ("Prix", _fmt(row["price"], "{:,.0f}")),
    ]
    kvh = "".join(f"<span class='lbl'>{k}</span><span>{v}</span>" for k, v in kv)
    flags = (f"<span class='flag {'on' if row['trend_broken'] else ''}'>tendance {'CASSÉE' if row['trend_broken'] else 'OK'} (MM10 mois)</span>"
             f"<span class='flag {'on' if row['gsy'] else ''}'>bulle GSY {'ACTIVE' if row['gsy'] else 'non'}</span>"
             + (f"<span class='flag on'>couteau qui tombe</span>" if row.get("falling_knife", False) else ""))
    return (f"<section class='card'><div class='head'><div class='dot {c}'></div><div><div class='name'>{html.escape(name)}</div>"
            f"<div class='state {c}'>{LABEL[c]}</div></div></div><div class='since'>depuis le {_since(df)} · données au {df.index[-1]:%d/%m/%Y}</div>"
            f"<div class='reason'>{html.escape(row['reason']) if row['reason'] else 'aucune condition extrême : état normal ou ambigu'}</div>"
            f"<div>{flags}</div><div class='kv'>{kvh}</div>"
            f"<details><summary>Explication</summary><div class='expl'>{html.escape(explain_index(name, row))}</div></details>"
            f"{_timeline_svg(df, '1990-01-01')}</section>")


def _card_btc(df: pd.DataFrame) -> str:
    row = df.iloc[-1]
    c = row["color"]
    kv = [
        ("Valorisation V (σ)", _fmt(row["V"], "{:+.2f}")), ("— prix / MM200 semaines", _fmt(row["ratio_200w"], "{:.2f}", "x") + f" · z {_fmt(row['z_ratio_200w'], '{:+.2f}')}"),
        ("— MVRV", _fmt(row["mvrv"], "{:.2f}") + f" · z {_fmt(row['z_mvrv'], '{:+.2f}')}"),
        ("Baisse depuis le record", _fmt(row["drawdown"], "{:.0f}", " %", 100)), ("Fear & Greed (30 j)", _fmt(row["fng_30d"])),
        ("Écart MM200 jours", _fmt(row["gap_ma200d"], "{:+.0f}", " %", 100)), ("Prix", _fmt(row["price"], "{:,.0f}", " $")),
    ]
    kvh = "".join(f"<span class='lbl'>{k}</span><span>{v}</span>" for k, v in kv)
    flags = (f"<span class='flag {'on' if row['trend_broken'] else ''}'>tendance {'CASSÉE' if row['trend_broken'] else 'OK'} (MM200 j)</span>"
             f"<span class='flag {'on' if row['gsy'] else ''}'>bulle GSY {'ACTIVE' if row['gsy'] else 'non'}</span>")
    return (f"<section class='card'><div class='head'><div class='dot {c}'></div><div><div class='name'>Bitcoin</div>"
            f"<div class='state {c}'>{LABEL[c]}</div></div></div><div class='since'>depuis le {_since(df)} · données au {df.index[-1]:%d/%m/%Y}</div>"
            f"<div class='reason'>{html.escape(row['reason']) if row['reason'] else 'aucune condition extrême : état normal ou ambigu'}</div>"
            f"<div>{flags}</div><div class='kv'>{kvh}</div>"
            f"<details><summary>Explication</summary><div class='expl'>{html.escape(explain_btc(row))}</div></details>"
            f"{_timeline_svg(df, '2014-01-01')}</section>")


def _conduct_table() -> str:
    rows = ""
    for color in ["green", "orange", "red"]:
        items = "".join(f"<li>{html.escape(t)}</li>" for t in conduct_text(color))
        rows += f"<tr><td class='c {color}'>{LABEL[color]}</td><td><ul style='margin:0;padding-left:18px'>{items}</ul></td></tr>"
    tb = rules()["conduct"]["trend_broken"]
    rows += (f"<tr><td class='c'>Tendance cassée<br><small>(toute couleur)</small></td><td>Clôture mensuelle sous la moyenne 10 mois : levier ramené à "
             f"{100 * tb['leverage_cap_share_equities']:.0f} % au plus de la poche actions sous {tb['action_within_trading_days']} jours de bourse. "
             f"Bitcoin : sous la MM200 jours, aucun proxy à levier.</td></tr>")
    return f"<table><tr><th style='width:140px'>Couleur</th><th>Règles de conduite (rules.yaml)</th></tr>{rows}</table>"


def _validation_summary() -> str:
    p = DOCS_DIR / "backtest_summary.json"
    if not p.exists():
        return "<p>Backtest non exécuté.</p>"
    s = json.loads(p.read_text(encoding="utf-8"))
    names = {**{k: v["name"] for k, v in rules()["indices"]["assets"].items()}, "btc": "Bitcoin"}
    rows = ""
    for a, name in names.items():
        if a not in s:
            continue
        f3 = {r["couleur"]: r for r in s[a]["fwd"] if r["horizon"] == "3 ans"}
        dd = {r["couleur"]: r for r in s[a]["dd24"]}
        eps = s[a]["checks"]["épisodes_ok"]
        rows += (f"<tr><td>{name}</td>"
                 + "".join(f"<td class='c {c}'>{100 * s[a]['share'][c]:.0f} %</td>" for c in ["green", "orange", "red"])
                 + "".join(f"<td>{100 * f3[c]['médiane_annualisée']:+.1f} %</td>" if c in f3 else "<td>–</td>" for c in ["green", "orange", "red"])
                 + "".join(f"<td>{100 * dd[c]['drawdown_24m_médian']:.0f} %</td>" if c in dd else "<td>–</td>" for c in ["green", "orange", "red"])
                 + f"<td>{eps['valeur']}/{eps['total']}</td></tr>")
    return ("<table><tr><th rowspan='2'>Actif</th><th colspan='3'>Part du temps</th><th colspan='3'>Rendement médian annualisé, 3 ans suivants</th>"
            "<th colspan='3'>Baisse médiane dans les 24 mois</th><th rowspan='2'>Épisodes reproduits</th></tr>"
            "<tr>" + "".join(f"<th class='c {c}'>{LABEL[c]}</th>" for c in ["green", "orange", "red"]) * 3 + "</tr>" + rows + "</table>")


def build() -> None:
    r = rules()
    cards = []
    dfs = {}
    for key, spec in r["indices"]["assets"].items():
        dfs[key] = load_signals(key)
        cards.append(_card_index(key, spec["name"], dfs[key]))
    dfs["btc"] = load_signals("btc")
    cards.append(_card_btc(dfs["btc"]))
    now = dt.datetime.now(dt.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    page = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Feux tricolores — investissement long terme</title><style>{CSS}</style></head><body><main>
<h1>Feux tricolores</h1><p class="sub">Lecture générée le {now} · règles gelées le {r['frozen_at']} (v{r['version']}) · <a href="backtest.html">validation 1990-2026</a> · <a href="latest.json">données brutes</a></p>
<div class="warn">Un feu mesure un <b>état</b> (cher / tendu / euphorique, ou décoté / capitulation), pas une prévision. Il gouverne le levier, les montants exceptionnels et le rééquilibrage. Les versements réguliers ne s'arrêtent jamais, quelle que soit la couleur.</div>
<h2>Lecture du jour</h2><div class="grid">{''.join(cards)}</div>
<p class="legend"><i style="background:{HEX['green']}"></i>vert <i style="background:{HEX['orange']}"></i>orange <i style="background:{HEX['red']}"></i>rouge — frise mensuelle depuis 1990 (Bitcoin : 2014)</p>
<h2>Ce que chaque couleur autorise</h2>{_conduct_table()}
<h2>Ce que les feux ont donné dans le passé (point-in-time)</h2>{_validation_summary()}
<p class="sub">Rendements de prix hors dividendes ; chaque jour est classé par sa couleur du jour. Détails, épisodes, coût des faux positifs et simulation du levier x2 : <a href="backtest.html">rapport complet</a>.</p>
<footer>Sources : Robert Shiller (shillerdata.com) ; FRED (VIX, BAA10Y, TB3MS, séries Z.1) ; Yahoo Finance (^GSPC, ^NDX/^IXIC, ^990100-USD-STRD) ; FINRA (dette sur marge) ; Coin Metrics Community (prix, MVRV, CC BY-NC 4.0) ; alternative.me (Fear &amp; Greed).
Outil personnel, déterministe, sans conseil en investissement. Code et règles : voir le dépôt.</footer></main></body></html>"""
    (DOCS_DIR / "index.html").write_text(page, encoding="utf-8")
    (DOCS_DIR / ".nojekyll").write_text("")
    log.info("Tableau de bord : %s", DOCS_DIR / "index.html")
