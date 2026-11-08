"""Tableau de bord statique (docs/index.html), autonome, sans dépendance externe."""
from __future__ import annotations

import datetime as dt
import html
import json
import logging

import pandas as pd

from .config import DOCS_DIR, rules
from .explain import conduct_text, explain_btc, explain_index
from .plain import GLOSSARY, headline, monthly_actions, simple_btc, simple_index
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
body[data-mode=simple] .detail-only{display:none}body[data-mode=detail] .simple-only{display:none}
.toggle{display:inline-flex;border:1px solid var(--line);border-radius:999px;overflow:hidden;font-size:13px;margin-left:8px;vertical-align:middle}
.toggle button{border:0;background:#fff;padding:5px 12px;cursor:pointer;color:var(--muted)}.toggle button.on{background:#1f2328;color:#fff}
.headline{font-size:17px;font-weight:600;margin:14px 0 6px}.actions{background:#f0f7f0;border:1px solid #cfe5cf;border-radius:10px;padding:12px 16px}
.actions li{margin:4px 0}.plain{font-size:15px;line-height:1.55}.gloss dt{font-weight:650;margin-top:12px}.gloss dd{margin:2px 0 0 0;color:#333}
.gloss .rule{display:block;color:var(--muted);font-size:13px;margin-top:2px}abbr{text-decoration:underline dotted;cursor:help}
"""

LABEL = {"green": "VERT", "orange": "ORANGE", "red": "ROUGE"}
HEX = {"green": "#1a7f37", "orange": "#c7641a", "red": "#b3261e"}


def _since(df: pd.DataFrame) -> str:
    col = df["color_confirmed"]
    last = col.iloc[-1]
    changes = col[col != last]
    start = col.index[0] if changes.empty else col.index[col.index.get_loc(changes.index[-1]) + 1]
    return start.strftime("%d/%m/%Y")


def _timeline_svg(df: pd.DataFrame, start: str) -> str:
    d = df[df.index >= start]["color_confirmed"].resample("ME").last().dropna()
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


def _raw_note(row) -> str:
    if row["color"] != row["color_confirmed"]:
        return f"<div class='since'>état brut du jour : <b>{LABEL[row['color']]}</b> (confirmé après 5 jours consécutifs)</div>"
    return ""


TIPS = {
    "Valorisation V": "Médiane des percentiles 25 ans de trois mesures : CAPE, Excess CAPE Yield, allocation actions des ménages. 80 et plus = cher.",
    "— CAPE (vivant)": "Prix payé pour 1 € de bénéfice moyen des 10 dernières années (inflation corrigée). p = percentile 25 ans.",
    "— Excess CAPE Yield": "Rendement des actions (1/CAPE) moins le taux réel à 10 ans : ce que les actions rapportent en plus du sans-risque.",
    "— Allocation actions (AIAE)": "Part du patrimoine financier des ménages américains déjà placée en actions.",
    "Extension X": "Médiane des percentiles de l'écart à la moyenne 200 jours et de la performance 12 mois ; 100 si le critère de bulle GSY est actif.",
    "— écart MM200 j": "Prix du jour par rapport au prix moyen des 200 derniers jours de bourse.",
    "— perf. 12 mois": "Variation sur un an.",
    "Euphorie E (dette sur marge)": "Croissance annuelle de l'argent emprunté par les investisseurs américains pour acheter des actions (percentile depuis 1997 ; 100 si ≥ +50 %).",
    "Peur P": "Médiane des percentiles du VIX et du spread de crédit : confirme un vert de capitulation.",
    "Baisse depuis le plus haut": "Écart au record historique.",
    "Prix": "Dernière clôture.",
    "Valorisation V (σ)": "Moyenne de deux z-scores 4 ans (log) : prix / moyenne 200 semaines et MVRV. ≥ +1 = cher ; ≤ −0,5 = décoté.",
    "— prix / MM200 semaines": "Prix rapporté à son prix moyen des quatre dernières années (plancher historique des marchés baissiers).",
    "— MVRV": "Prix rapporté au prix moyen payé par les détenteurs actuels.",
    "Baisse depuis le record": "Écart au record historique.",
    "Fear & Greed (30 j)": "Indice crypto 0 (peur extrême) à 100 (avidité extrême), moyenne 30 jours.",
    "Financement 30 j": "Taux de financement quotidien moyen du perpétuel BTC (Deribit) et son percentile : élevé = euphorie à crédit.",
    "Écart MM200 jours": "Prix du jour par rapport au prix moyen des 200 derniers jours.",
}


def _kv_html(kv: list[tuple[str, str]]) -> str:
    out = []
    for k, v in kv:
        tip = TIPS.get(k)
        label = f"<abbr title='{html.escape(tip)}'>{k}</abbr>" if tip else k
        out.append(f"<span class='lbl'>{label}</span><span>{v}</span>")
    return "".join(out)


def _card_index(key: str, name: str, df: pd.DataFrame) -> str:
    row = df.iloc[-1]
    c = row["color_confirmed"]
    kv = [
        ("Valorisation V", _fmt(row["V"])), ("— CAPE (vivant)", _fmt(row["cape_live"], "{:.1f}") + f" · p{_fmt(row['cape_pct'])}"),
        ("— Excess CAPE Yield", _fmt(row["ecy_live"], "{:.2f}", " %", 100)), ("— Allocation actions (AIAE)", _fmt(row["aiae"], "{:.1f}", " %", 100) + f" · p{_fmt(row['aiae_pct'])}"),
        ("Extension X", _fmt(row["X"])), ("— écart MM200 j", _fmt(row["gap_ma200"], "{:+.1f}", " %", 100)), ("— perf. 12 mois", _fmt(row["mom_12m"], "{:+.1f}", " %", 100)),
        ("Euphorie E (dette sur marge)", _fmt(row["E"]) + f" · {_fmt(row['margin_yoy'], '{:+.0f}', ' %/an', 100)}"),
        ("Peur P", _fmt(row["P"]) + f" · VIX {_fmt(row['vix'], '{:.1f}')}"), ("Baisse depuis le plus haut", _fmt(row["drawdown"], "{:.1f}", " %", 100)),
        ("Prix", _fmt(row["price"], "{:,.0f}")),
    ]
    kvh = _kv_html(kv)
    flags = (f"<span class='flag {'on' if row['trend_broken'] else ''}'>tendance {'CASSÉE' if row['trend_broken'] else 'OK'} (MM10 mois)</span>"
             f"<span class='flag {'on' if row['gsy'] else ''}'>bulle GSY {'ACTIVE' if row['gsy'] else 'non'}</span>"
             + (f"<span class='flag on'>couteau qui tombe</span>" if row.get("falling_knife", False) else ""))
    return (f"<section class='card'><div class='head'><div class='dot {c}'></div><div><div class='name'>{html.escape(name)}</div>"
            f"<div class='state {c}'>{LABEL[c]}</div></div></div><div class='since'>depuis le {_since(df)} · données au {df.index[-1]:%d/%m/%Y}</div>"
            f"<div class='plain simple-only'>{html.escape(simple_index(key, row))}</div>"
            f"<div class='reason detail-only'>{html.escape(row['reason']) if row['reason'] else 'aucune condition extrême : état normal ou ambigu'}</div>{_raw_note(row)}"
            f"<div class='detail-only'>{flags}</div><div class='kv detail-only'>{kvh}</div>"
            f"<details class='detail-only'><summary>Explication chiffrée</summary><div class='expl'>{html.escape(explain_index(name, row))}</div></details>"
            f"{_timeline_svg(df, '1990-01-01')}</section>")


def _card_btc(df: pd.DataFrame) -> str:
    row = df.iloc[-1]
    c = row["color_confirmed"]
    kv = [
        ("Valorisation V (σ)", _fmt(row["V"], "{:+.2f}")), ("— prix / MM200 semaines", _fmt(row["ratio_200w"], "{:.2f}", "x") + f" · z {_fmt(row['z_ratio_200w'], '{:+.2f}')}"),
        ("— MVRV", _fmt(row["mvrv"], "{:.2f}") + f" · z {_fmt(row['z_mvrv'], '{:+.2f}')}"),
        ("Baisse depuis le record", _fmt(row["drawdown"], "{:.0f}", " %", 100)), ("Fear & Greed (30 j)", _fmt(row["fng_30d"])),
        ("Financement 30 j", _fmt(row.get("funding_30d"), "{:.3f}", " %/j", 100) + f" · p{_fmt(row.get('funding_pct'))}"),
        ("Écart MM200 jours", _fmt(row["gap_ma200d"], "{:+.0f}", " %", 100)), ("Prix", _fmt(row["price"], "{:,.0f}", " $")),
    ]
    kvh = _kv_html(kv)
    flags = (f"<span class='flag {'on' if row['trend_broken'] else ''}'>tendance {'CASSÉE' if row['trend_broken'] else 'OK'} (MM200 j)</span>"
             f"<span class='flag {'on' if row['gsy'] else ''}'>bulle GSY {'ACTIVE' if row['gsy'] else 'non'}</span>")
    return (f"<section class='card'><div class='head'><div class='dot {c}'></div><div><div class='name'>Bitcoin</div>"
            f"<div class='state {c}'>{LABEL[c]}</div></div></div><div class='since'>depuis le {_since(df)} · données au {df.index[-1]:%d/%m/%Y}</div>"
            f"<div class='plain simple-only'>{html.escape(simple_btc(row))}</div>"
            f"<div class='reason detail-only'>{html.escape(row['reason']) if row['reason'] else 'aucune condition extrême : état normal ou ambigu'}</div>{_raw_note(row)}"
            f"<div class='detail-only'>{flags}</div><div class='kv detail-only'>{kvh}</div>"
            f"<details class='detail-only'><summary>Explication chiffrée</summary><div class='expl'>{html.escape(explain_btc(row))}</div></details>"
            f"{_timeline_svg(df, '2014-01-01')}</section>")


def _stocks_section() -> str:
    from .stocks import load_all, watchlist

    res = load_all()
    if not res:
        return ("<p class='sub'>Module actions non exécuté (définir <code>SEC_USER_AGENT</code> puis <code>python -m feux stocks</code>). "
                "Liste de suivi : <code>stocks.yaml</code>.</p>")
    wl = watchlist()
    rows = ""
    for key, df in res.items():
        spec = wl.get(key, {"name": key, "type": "?"})
        row = df.iloc[-1]
        c = row["color_confirmed"]
        kind = spec.get("type", "operating")
        if kind == "operating":
            val = (f"EV/EBIT {_fmt(row.get('ev_ebit'), '{:.1f}')} (p{_fmt(row.get('ev_ebit_pct'))}) · P/FCF {_fmt(row.get('p_fcf'), '{:.1f}')} (p{_fmt(row.get('p_fcf_pct'))}) · V {_fmt(row.get('V'))}")
            qual = (f"ROIC {_fmt(row.get('roic'), '{:.0f}', ' %', 100)} · FCF/RN {_fmt(row.get('fcf_ni'), '{:.2f}')} · DN/EBITDA {_fmt(row.get('nd_ebitda'), '{:.1f}')} → "
                    + ("<b>OK</b>" if bool(row.get("quality_ok", False)) else "<b style='color:var(--red)'>échec</b>"))
            growth = f"implicite {_fmt(row.get('implied_growth'), '{:+.0f}', ' %/an', 100)} vs réalisée 5 ans {_fmt(row.get('fcf_cagr_5y'), '{:+.0f}', ' %/an', 100)}"
        elif kind == "crypto_proxy":
            val, qual, growth = "suit le feu Bitcoin", "—", "prime sur la trésorerie BTC (mNAV) : non calculée"
        else:
            val, qual, growth = "hors EDGAR : valorisation n.d.", "—", "—"
        ext = f"MM200 {_fmt(row.get('gap_ma200'), '{:+.0f}', ' %', 100)} · GSY {'oui' if bool(row.get('gsy', False)) else 'non'} · tendance {'cassée' if bool(row.get('trend_broken', False)) else 'OK'}"
        rows += (f"<tr><td><b>{html.escape(spec['name'])}</b><br><small>{key} · {kind}</small></td><td class='c {c}'>{LABEL[c]}</td>"
                 f"<td>{val}</td><td>{qual}</td><td>{growth}</td><td>{ext}</td><td>{_fmt(row.get('drawdown'), '{:.0f}', ' %', 100)}</td><td>{df.index[-1]:%d/%m/%Y}</td></tr>")
    return ("<table><tr><th>Société</th><th>Feu</th><th>Valorisation (percentiles 10 ans)</th><th>Qualité (éliminatoire)</th>"
            "<th>Croissance du FCF</th><th>Extension / tendance</th><th>Baisse vs plus haut</th><th>Données au</th></tr>" + rows + "</table>"
            "<p class='sub'>Rouge = valorisation ≥ 80e percentile ET (hausse ≥100 %/2 ans avec accélération OU écart MM200 ≥ 90e percentile) ; "
            "vert = valorisation ≤ 30e percentile ET filtre qualité réussi. Comptes SEC EDGAR datés du dépôt (point-in-time), première publication conservée.</p>")


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


def _glossary() -> str:
    items = "".join(f"<dt>{html.escape(t)}</dt><dd>{html.escape(d)}<span class='rule'>Dans les règles : {html.escape(rl)}</span></dd>" for t, d, rl in GLOSSARY)
    return f"<dl class='gloss'>{items}</dl>"


def _states(dfs: dict[str, pd.DataFrame]) -> dict:
    r = rules()
    st = {}
    for key, df in dfs.items():
        row = df.iloc[-1]
        st[key] = {"name": r["indices"]["assets"].get(key, {}).get("name", "Bitcoin"), "color": row["color_confirmed"],
                   "trend_broken": bool(row["trend_broken"]), "falling_knife": bool(row.get("falling_knife", False))}
    return st


TOGGLE_JS = """<script>(function(){var b=document.body;var m='simple';try{m=localStorage.getItem('feux-mode')||'simple';}catch(e){}
function set(x){b.setAttribute('data-mode',x);document.querySelectorAll('.toggle button').forEach(function(k){k.classList.toggle('on',k.dataset.m===x);});try{localStorage.setItem('feux-mode',x);}catch(e){}}
set(m);document.querySelectorAll('.toggle button').forEach(function(k){k.addEventListener('click',function(){set(k.dataset.m);});});})();</script>"""


def build() -> None:
    r = rules()
    cards = []
    dfs = {}
    for key, spec in r["indices"]["assets"].items():
        dfs[key] = load_signals(key)
        cards.append(_card_index(key, spec["name"], dfs[key]))
    dfs["btc"] = load_signals("btc")
    cards.append(_card_btc(dfs["btc"]))
    states = _states(dfs)
    acts = "".join(f"<li>{html.escape(a)}</li>" for a in monthly_actions(states))
    now = dt.datetime.now(dt.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    page = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Feux tricolores — investissement long terme</title><style>{CSS}</style></head><body data-mode="simple"><main>
<h1>Feux tricolores <span class="toggle"><button data-m="simple">Mode simple</button><button data-m="detail">Mode détaillé</button></span></h1><p class="sub">Lecture générée le {now} · règles gelées le {r['frozen_at']} (v{r['version']}) · <a href="backtest.html">validation 1990-2026</a> · <a href="robustness.html">robustesse</a> · <a href="latest.json">données brutes</a></p>
<div class="warn">Un feu mesure un <b>état</b> (cher / tendu / euphorique, ou décoté / capitulation), pas une prévision. Il gouverne le levier, les montants exceptionnels et le rééquilibrage. Les versements réguliers ne s'arrêtent jamais, quelle que soit la couleur.</div>
<p class="headline">{html.escape(headline(states))}</p>
<div class="actions"><b>Ce mois-ci, concrètement</b><ul style="margin:6px 0 0;padding-left:18px">{acts}</ul></div>
<h2>Lecture du jour</h2><div class="grid">{''.join(cards)}</div>
<p class="legend"><i style="background:{HEX['green']}"></i>vert <i style="background:{HEX['orange']}"></i>orange <i style="background:{HEX['red']}"></i>rouge — frise mensuelle depuis 1990 (Bitcoin : 2014)</p>
<h2>Actions suivies</h2>{_stocks_section()}
<h2>Ce que chaque couleur autorise</h2>{_conduct_table()}
<h2>Ce que les feux ont donné dans le passé (point-in-time)</h2>{_validation_summary()}
<p class="sub">Rendements de prix hors dividendes ; chaque jour est classé par sa couleur du jour. Détails, épisodes, coût des faux positifs et simulation du levier x2 : <a href="backtest.html">rapport complet</a>.</p>
<h2 id="glossaire">Les mots et les chiffres, expliqués</h2>
<p class="sub">Chaque indicateur du tableau de bord, en langage courant, avec ce que la règle en fait. Les seuils exacts sont dans <code>rules.yaml</code>.</p>
{_glossary()}
<footer>Sources : Robert Shiller (shillerdata.com) ; FRED (VIX, BAA10Y, TB3MS, séries Z.1) ; Yahoo Finance (^GSPC, ^NDX/^IXIC, ^990100-USD-STRD) ; FINRA (dette sur marge) ; Coin Metrics Community (prix, MVRV, CC BY-NC 4.0) ; alternative.me (Fear &amp; Greed).
Outil personnel, déterministe, sans conseil en investissement. Code et règles : voir le dépôt.</footer></main>{TOGGLE_JS}</body></html>"""
    (DOCS_DIR / "index.html").write_text(page, encoding="utf-8")
    (DOCS_DIR / ".nojekyll").write_text("")
    log.info("Tableau de bord : %s", DOCS_DIR / "index.html")
