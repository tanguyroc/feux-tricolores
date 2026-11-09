"""Tableau de bord statique (docs/index.html), autonome, sans dépendance externe."""
from __future__ import annotations

import datetime as dt
import html
import json
import logging

import pandas as pd

from .config import DOCS_DIR, rules
from .explain import conduct_text, explain_btc, explain_index
from .plain import GLOSSARY, headline, monthly_actions, simple_btc, simple_index, since_sentence
from .signals import load_signals

log = logging.getLogger("feux.dashboard")

CSS = """
.src{font-size:11px;color:var(--muted);margin-top:8px;line-height:1.4}
.since-perf{font-size:13px;margin:6px 0;padding:6px 8px;background:#f6f6f2;border-radius:6px}
.honest{margin:12px 0;padding:10px 14px;border-left:4px solid #b3261e;background:#fff7f6;font-size:13px}.honest ul{margin:6px 0 0 18px}
td.ok{color:#2e7d32;font-weight:600}td.ko{color:#b3261e;font-weight:600}

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
.flag.info{border-color:#b35c00;color:#8a4500}
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
    "Valorisation V": "Percentile du CAPE du S&P 500 parmi tous les mois depuis 1881 (fenêtre croissante). 40 ou moins = vert ; 80 ou plus = « cher » (information).",
    "Valorisation V (S&P 500, proxy)": "Valorisation du S&P 500 utilisée comme repère : pas d'historique long de valorisation pour cet indice.",
    "— CAPE": "Prix payé pour 1 € de bénéfice moyen des 10 dernières années (inflation corrigée), recalé chaque jour sur le prix.",
    "— CAPE du S&P 500": "CAPE du S&P 500, utilisé comme repère pour cet indice.",
    "— rendement réel attendu 10 ans": "Régression historique (1881-2016) du rendement réel à 10 ans sur le CAPE, réestimée chaque mois ; fourchette 80 %. Trop pessimiste d'environ 5 points/an depuis 1990.",
    "Peur P (capitulation)": "Médiane des percentiles du VIX et du spread de crédit : confirme un vert de capitulation (≥ 80 avec une baisse ≥ 25 %).",
    "Baisse depuis le plus haut": "Écart au record historique.",
    "Par le bas — P/E de ses plus grosses sociétés": "Prix payé pour 1 € de bénéfice des 12 derniers mois, agrégé sur les sociétés de l'indice présentes dans le Top 100 (pondération MSCI). Aujourd'hui seulement, sans historique : contexte.",
    "Par le bas — vs leur propre passé": "Moyenne pondérée de la jauge de chaque société contre ses dix dernières années (0 = la moins chère de son histoire). Contexte.",
    "Contexte — écart MM200 j": "Prix du jour par rapport au prix moyen des 200 derniers jours ; p = percentile sur tout l'historique (≥ 15 ans). Hors règle.",
    "Contexte — perf. 12 mois": "Variation sur un an. Hors règle.",
    "Contexte — excess CAPE yield": "Rendement des actions (1/CAPE) moins le taux réel à 10 ans. Hors règle depuis la v1.0.",
    "Contexte — allocation des ménages": "Part du patrimoine financier des ménages américains placée en actions (Fed, trimestriel). Hors règle depuis la v1.0.",
    "Contexte — dette sur marge": "Croissance annuelle de l'argent emprunté pour acheter des actions (FINRA, mensuel). Hors règle depuis la v1.0.",
    "Prix": "Dernière clôture.",
    "MVRV (règle : vert < 1, rouge ≥ 3)": "Prix rapporté au prix moyen payé par les détenteurs actuels (Coin Metrics).",
    "Prix / moyenne 200 semaines (vert < 1)": "Prix rapporté à son prix moyen des quatre dernières années (plancher historique des marchés baissiers).",
    "Baisse depuis le record": "Écart au record historique.",
    "Écart MM200 jours (proxys à levier)": "Sous zéro : tendance cassée, pas de société « proxy » à levier.",
    "Contexte — z-scores 4 ans": "Ancienne règle (v0.x) : écart à la normale des quatre dernières années, prix/MM200s puis MVRV. Hors règle.",
    "Contexte — Fear & Greed 30 j": "Indice crypto 0 (peur extrême) à 100 (avidité extrême), moyenne 30 jours. Hors règle.",
    "Contexte — financement 30 j": "Taux de financement du perpétuel BTC (Deribit) et son percentile. Hors règle.",
}


def _kv_html(kv: list[tuple[str, str]]) -> str:
    out = []
    for k, v in kv:
        tip = TIPS.get(k)
        label = f"<abbr title='{html.escape(tip)}'>{k}</abbr>" if tip else k
        out.append(f"<span class='lbl'>{label}</span><span>{v}</span>")
    return "".join(out)


def _latest_extras(key: str) -> dict:
    """Champs calculés à l'enregistrement (début de l'état, performance depuis, dates de référence des séries en retard)."""
    try:
        return json.loads((DOCS_DIR / "latest.json").read_text(encoding="utf-8")).get(key, {})
    except Exception:
        return {}


_BU: dict | None = None


def _bottom_up() -> dict:
    global _BU
    if _BU is None:
        try:
            from .stocks import bottom_up_by_index
            _BU = bottom_up_by_index()
        except Exception:   # module actions absent : pas bloquant
            _BU = {}
    return _BU


def _row_with_extras(key: str, df: pd.DataFrame) -> pd.Series:
    row = df.iloc[-1].copy()
    for k, v in _latest_extras(key).items():
        if k not in row.index or k in ("state_since", "state_days", "perf_since_state"):
            row[k] = v
    bu = _bottom_up()
    if key in bu:
        row["bu_n"], row["bu_pe"], row["bu_v_own"] = bu[key]["n"], bu[key]["pe"], bu[key]["v_own"]
        row["bu_pe_sp500"] = bu.get("sp500", {}).get("pe")
    return row


def _fr(d) -> str:
    try:
        return pd.Timestamp(d).strftime("%d/%m/%Y")
    except Exception:
        return str(d)


def _card_index(key: str, name: str, df: pd.DataFrame) -> str:
    row = _row_with_extras(key, df)
    c = row["color_confirmed"]
    proxy = bool(row.get("valuation_is_proxy", False))
    aiae_when = f" · au {_fr(row['aiae_ref_date'])}" if row.get("aiae_ref_date") else ""
    margin_when = f" · au {_fr(row['margin_ref_date'])}" if row.get("margin_ref_date") else ""
    er = row.get("er10")
    er_txt = "n.d." if er is None or pd.isna(er) else f"{100 * er:+.1f} %/an ({100 * row['er10_lo']:+.0f} à {100 * row['er10_hi']:+.0f})"
    kv = [
        ("Valorisation V" + (" (S&P 500, proxy)" if proxy else ""), _fmt(row["V"]) + "e percentile depuis 1881"),
        ("— CAPE" + (" du S&P 500" if proxy else ""), _fmt(row["cape_live"], "{:.1f}")),
        ("— rendement réel attendu 10 ans", er_txt),
        ("Peur P (capitulation)", _fmt(row["P"]) + f" · VIX {_fmt(row['vix'], '{:.1f}')}"),
        ("Baisse depuis le plus haut", _fmt(row["drawdown"], "{:.1f}", " %", 100)),
        ("Par le bas — P/E de ses plus grosses sociétés", (_fmt(row.get("bu_pe"), "{:.1f}") + f" ({_fmt(row.get('bu_n'))} sociétés)") if row.get("bu_pe") else "n.d."),
        ("Par le bas — vs leur propre passé", ("p" + _fmt(row.get("bu_v_own"))) if row.get("bu_v_own") is not None else "n.d."),
        ("Contexte — écart MM200 j", _fmt(row["gap_ma200"], "{:+.1f}", " %", 100) + f" · p{_fmt(row.get('x_hist_pct'))}"),
        ("Contexte — perf. 12 mois", _fmt(row["mom_12m"], "{:+.1f}", " %", 100)),
        ("Contexte — excess CAPE yield", _fmt(row["ecy_live"], "{:.2f}", " %", 100)),
        ("Contexte — allocation des ménages", _fmt(row["aiae"], "{:.1f}", " %", 100) + aiae_when),
        ("Contexte — dette sur marge", _fmt(row["margin_yoy"], "{:+.0f}", " %/an", 100) + margin_when),
        ("Prix", _fmt(row["price"], "{:,.0f}")),
    ]
    kvh = _kv_html(kv)
    flags = (f"<span class='flag {'on' if row['trend_broken'] else ''}'>tendance {'CASSÉE' if row['trend_broken'] else 'OK'} (MM10 mois)</span>"
             + (f"<span class='flag info'>cher</span>" if row.get("cher", False) else "")
             + (f"<span class='flag info'>cher et tendu (information)</span>" if row.get("cher_tendu", False) else "")
             + (f"<span class='flag info'>hausse ≥ 100 % en 2 ans (contexte)</span>" if row.get("gsy", False) else "")
             + (f"<span class='flag on'>couteau qui tombe</span>" if row.get("falling_knife", False) else ""))
    tag = " · cher" if (c == "orange" and row.get("cher", False)) else ""
    return (f"<section class='card'><div class='head'><div class='dot {c}'></div><div><div class='name'>{html.escape(name)}</div>"
            f"<div class='state {c}'>{LABEL[c]}{tag}</div></div></div><div class='since'>depuis le {_since(df)} · données au {df.index[-1]:%d/%m/%Y}</div>"
            f"<div class='plain simple-only'>{html.escape(simple_index(key, row))}</div>"
            + (f"<div class='since-perf'>{html.escape(since_sentence(row))}</div>" if since_sentence(row) else "")
            + (f"<div class='note'>Valorisation mesurée sur le S&P 500 : proxy, faute d'historique long de valorisation pour cet indice.</div>" if proxy else "")
            + f"<div class='reason detail-only'>{html.escape(row['reason']) if row['reason'] else 'aucune condition extrême'}</div>{_raw_note(row)}"
            f"<div class='flags'>{flags}</div><div class='kv detail-only'>{kvh}</div>"
            f"<details class='detail-only'><summary>Explication chiffrée</summary><div class='expl'>{html.escape(explain_index(name, row))}</div></details>"
            f"<div class='src detail-only'>Sources : prix Yahoo Finance au {df.index[-1]:%d/%m/%Y} · CAPE et bénéfices de R. Shiller (mensuels), "
            f"actualisés chaque jour par le prix · VIX et écart de crédit FRED · allocation des ménages Fed Z.1{aiae_when} · "
            f"dette sur marge FINRA{margin_when} · « par le bas » : comptes SEC EDGAR des plus grosses sociétés</div>"
            f"{_timeline_svg(df, '1990-01-01')}</section>")


def _card_btc(df: pd.DataFrame) -> str:
    row = _row_with_extras("btc", df)
    c = row["color_confirmed"]
    kv = [
        ("MVRV (règle : vert < 1, rouge ≥ 3)", _fmt(row["mvrv"], "{:.2f}")),
        ("Prix / moyenne 200 semaines (vert < 1)", _fmt(row["ratio_200w"], "{:.2f}", "×")),
        ("Baisse depuis le record", _fmt(row["drawdown"], "{:.0f}", " %", 100)),
        ("Écart MM200 jours (proxys à levier)", _fmt(row["gap_ma200d"], "{:+.0f}", " %", 100)),
        ("Contexte — z-scores 4 ans", _fmt(row["z_ratio_200w"], "{:+.2f}") + " / " + _fmt(row["z_mvrv"], "{:+.2f}")),
        ("Contexte — Fear & Greed 30 j", _fmt(row["fng_30d"])),
        ("Contexte — financement 30 j", _fmt(row.get("funding_30d"), "{:.3f}", " %/j", 100) + f" · p{_fmt(row.get('funding_pct'))}"),
        ("Prix", _fmt(row["price"], "{:,.0f}", " $")),
    ]
    kvh = _kv_html(kv)
    flags = (f"<span class='flag {'on' if row['trend_broken'] else ''}'>tendance {'CASSÉE' if row['trend_broken'] else 'OK'} (MM200 j)</span>"
             + (f"<span class='flag info'>hausse ≥ 100 % en 2 ans (contexte)</span>" if row.get("gsy", False) else ""))
    return (f"<section class='card'><div class='head'><div class='dot {c}'></div><div><div class='name'>Bitcoin</div>"
            f"<div class='state {c}'>{LABEL[c]}</div></div></div><div class='since'>depuis le {_since(df)} · données au {df.index[-1]:%d/%m/%Y}</div>"
            f"<div class='plain simple-only'>{html.escape(simple_btc(row))}</div>"
            + (f"<div class='since-perf'>{html.escape(since_sentence(row, 'le Bitcoin'))}</div>" if since_sentence(row, 'le Bitcoin') else "")
            + f"<div class='reason detail-only'>{html.escape(row['reason']) if row['reason'] else 'ni zone de capitulation ni euphorie (règle B1)'}</div>{_raw_note(row)}"
            f"<div class='flags'>{flags}</div><div class='kv detail-only'>{kvh}</div>"
            f"<details class='detail-only'><summary>Explication chiffrée</summary><div class='expl'>{html.escape(explain_btc(row))}</div></details>"
            f"<div class='src detail-only'>Sources : Coin Metrics Community au {df.index[-1]:%d/%m/%Y} (prix, MVRV ; licence CC BY-NC 4.0) · "
            f"Deribit (financement des contrats perpétuels) · alternative.me (Fear &amp; Greed)</div>"
            f"{_timeline_svg(df, '2014-01-01')}</section>")


def _themes_section() -> str:
    from .themes import load_all, simple_sentence

    res = load_all()
    if not res:
        return ""
    r = rules()["themes"]["assets"]
    lis = "".join(f"<li>{html.escape(simple_sentence(k, df.iloc[-1]))}</li>" for k, df in res.items())
    rows = ""
    for k, df in res.items():
        row = df.iloc[-1]
        rows += (f"<tr><td>{html.escape(r[k]['name'])}</td><td>{_fmt(row['runup_24m'], '{:+.0f}', ' %', 100)}</td>"
                 f"<td>{'OUI' if row['gsy'] else 'non'}</td><td>{_fmt(row['gap_ma200'], '{:+.0f}', ' %', 100)} (p{_fmt(row['gap_ma200_pct'])})</td>"
                 f"<td>{'cassée' if row['trend_broken'] else 'OK'}</td><td>{_fmt(row['drawdown'], '{:.0f}', ' %', 100)}</td><td>{df.index[-1]:%d/%m/%Y}</td></tr>")
    table = ("<table class='detail-only'><tr><th>Thème</th><th>Hausse 2 ans</th><th>Bulle GSY</th><th>Écart MM200 (percentile 25 ans)</th>"
             "<th>Tendance 10 mois</th><th>Baisse vs plus haut</th><th>Données au</th></tr>" + rows + "</table>")
    return (f"<h2>Les thèmes de votre portefeuille</h2><p class='sub'>Semi-conducteurs, éditeurs de logiciels, technologie américaine : des drapeaux, pas des couleurs "
            f"(sans mesure de valorisation sectorielle fiable, un thème n'est jamais « rouge »). Le critère de bulle a été établi sur des secteurs, c'est ici qu'il compte le plus.</p>"
            f"<ul class='plain' style='padding-left:18px'>{lis}</ul>{table}")


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
    # indices : vert et orange seulement depuis la v1.0 ; le rouge (Bitcoin) a sa propre ligne, plus bas
    for color, sub in (("green", ""), ("orange", "<br><small>(y compris « cher »)</small>")):
        items = "".join(f"<li>{html.escape(t)}</li>" for t in conduct_text(color))
        rows += f"<tr><td class='c {color}'>{LABEL[color]}{sub}</td><td><ul style='margin:0;padding-left:18px'>{items}</ul></td></tr>"
    cb = rules()["conduct"]["bitcoin"]
    rows += ("<tr><td class='c'>Bitcoin</td><td><ul style='margin:0;padding-left:18px'>"
             + "".join(f"<li><b class='c {c}'>{LABEL[c]}</b> : {html.escape(cb[c])}.</li>" for c in ("green", "orange", "red")) + "</ul></td></tr>")
    tb = rules()["conduct"]["trend_broken"]
    rows += (f"<tr><td class='c'>Tendance cassée<br><small>(toute couleur)</small></td><td>Clôture mensuelle sous la moyenne 10 mois : levier ramené à "
             f"{100 * tb['leverage_cap_share_equities']:.0f} % au plus de la poche actions sous {tb['action_within_trading_days']} jours de bourse. "
             f"Bitcoin : sous la MM200 jours, aucun proxy à levier.</td></tr>")
    return f"<table><tr><th style='width:140px'>Couleur</th><th>Règles de conduite (rules.yaml)</th></tr>{rows}</table>"


def episode_counts(key: str, min_days: int = 20) -> dict[str, int]:
    """Nombre d'épisodes distincts (séquences d'au moins `min_days` jours) par couleur confirmée : c'est l'effectif réel
    derrière chaque statistique, pas le nombre de jours (les jours d'un même épisode ne sont pas indépendants)."""
    try:
        df = load_signals(key)
    except Exception:
        return {}
    col = df["color_confirmed"] if "color_confirmed" in df else df["color"]
    runs = (col != col.shift()).cumsum()
    out = {"green": 0, "orange": 0, "red": 0}
    for _, grp in col.groupby(runs):
        if len(grp) >= min_days:
            out[grp.iloc[0]] = out.get(grp.iloc[0], 0) + 1
    return out


def _pct(x, signed=True, digits=1):
    if x is None or (isinstance(x, float) and x != x):
        return "–"
    return f"{100 * x:+.{digits}f} %" if signed else f"{100 * x:.0f} %"


def _protocol_section() -> str:
    """Résultats du protocole v1.0 (research/v1_protocol.md), tels que calculés en une seule exécution."""
    p = DOCS_DIR.parent / "research" / "longrun_summary_2026-11-09.json"   # résultats figés du 9 novembre 2026 (une seule exécution)
    if not p.exists():
        return "<p>Protocole non exécuté.</p>"
    o = json.loads(p.read_text(encoding="utf-8"))
    names = {"R1": "R1 cher et tendu", "R2": "R2 cher et cassé", "R3": "R3 très cher", "v0": "v0.6 (ancienne règle)"}

    def row(label, s):
        c = s.get("critères", {})
        mark = lambda k: "" if k not in c else (" ✓" if c[k] else " ✗")
        gap = s["écart_3ans"]
        gap_txt = "–" if gap is None else f"{100 * gap:+.1f} pts"
        return (f"<tr><td>{label}</td><td>{_pct(s['part']['red'], False)}</td><td>{s['épisodes']['red']}</td>"
                f"<td>{_pct(s['rdt_3ans']['green'])}</td><td>{_pct(s['rdt_3ans']['orange'])}</td><td>{_pct(s['rdt_3ans']['red'])}</td>"
                f"<td class='{'ok' if c.get('a_écart') else 'ko'}'>{gap_txt}{mark('a_écart')}</td>"
                f"<td>{_pct(s['baisse24m_p90']['orange'], False)} / {_pct(s['baisse24m_p90']['red'], False)}{mark('d_queue')}</td>"
                f"<td class='{'ok' if c.get('tout') else 'ko'}'>{'passe' if c.get('tout') else 'échoue'}</td></tr>")
    head = ("<tr><th>Règle rouge candidate</th><th>Rouge (part du temps)</th><th>Épisodes rouges</th><th>3 ans après vert</th><th>après orange</th>"
            "<th>après rouge</th><th>Écart vert − rouge (≥ 5 pts)</th><th>Pire baisse 24 mois (p90) orange / rouge</th><th>Critères</th></tr>")
    ho = "".join(row(names[v], o["hors_échantillon"][v]) for v in ("R1", "R2", "R3"))
    ds = "".join(row(names[v], o["conception_quotidienne"]["sp500"][v]) for v in ("v0", "R1", "R2", "R3"))
    nd = o["conception_quotidienne"]["ndx"]["R1"]
    return (f"<p><b>Protocole écrit et publié avant tout calcul</b> (research/v1_protocol.md, 9 novembre 2026, 07:40), une seule exécution. "
            f"Issue : <b>aucune règle rouge ne passe sur le S&P 500 depuis 1990</b>, alors que les trois passent sur 1920-1989. "
            f"Le rouge des indices devient donc l'étiquette d'information « cher ».</p>"
            f"<h3>Hors échantillon : S&P Composite 1920-1989 (mensuel, rendements réels dividendes inclus, jamais utilisé pour concevoir les feux)</h3>"
            f"<table>{head}{ho}</table>"
            f"<h3>Conception : S&P 500 1990-2026 (quotidien) — critère décisif</h3><table>{head}{ds}</table>"
            f"<p class='note'>Pourquoi : le CAPE a été au-dessus de son 80e percentile historique 88 % du temps depuis 1990, contre 20 % sur 1920-1989. "
            f"Observation non retenue (choisie après coup) : R1 passerait sur le Nasdaq-100 (écart {100 * nd['écart_3ans']:+.1f} pts) ; il est affiché comme drapeau "
            f"d'information et suivi en avant.</p>")


def _current_rules_section() -> str:
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
        ne = s[a].get("episodes_n", {})
        rows += (f"<tr><td>{name}</td>"
                 + "".join(f"<td class='c {c}'>{100 * s[a]['share'][c]:.0f} %<br><small>{ne.get(c, 0)} épisodes</small></td>" for c in ["green", "orange", "red"])
                 + "".join(f"<td>{100 * f3[c]['médiane_annualisée']:+.1f} %</td>" if c in f3 else "<td>–</td>" for c in ["green", "orange", "red"])
                 + "".join(f"<td>{100 * dd[c]['drawdown_24m_médian']:.0f} %<br><small>p90 {100 * dd[c]['drawdown_24m_p90']:.0f} %</small></td>" if c in dd else "<td>–</td>" for c in ["green", "orange", "red"])
                 + "</tr>")
    plan = s.get("plan_sp500", {})
    plan_txt = ""
    if plan:
        plan_txt = (f"<p class='note'>Plan type sur le S&P 500 depuis 1990 (1 000 €/mois + 10 000 €/an) : déployer l'exceptionnel en trois tranches mensuelles "
                    f"(règle v1.0) coûte {_pct(plan.get('C_moins_A_pct'))} par rapport à un investissement immédiat ; attendre le vert aurait coûté "
                    f"{_pct(plan.get('B_moins_A_pct'))}. Nasdaq-100 : attendre le vert {_pct(s.get('plan_ndx', {}).get('B_moins_A_pct'))}.</p>")
    return ("<table><tr><th rowspan='2'>Actif</th><th colspan='3'>Part du temps (et épisodes ≥ 20 jours)</th><th colspan='3'>Rendement médian annualisé, 3 ans suivants</th>"
            "<th colspan='3'>Baisse médiane (et p90) dans les 24 mois</th></tr>"
            "<tr>" + "".join(f"<th class='c {c}'>{LABEL[c]}</th>" for c in ["green", "orange", "red"]) * 3 + "</tr>" + rows + "</table>"
            "<p class='note'>Indices : vert = valorisation basse ou capitulation ; plus de rouge depuis la v1.0. Le vert n'a été suivi que de rendements "
            "modérément meilleurs que l'orange depuis 1990 (+1 à +3 points par an selon l'indice) ; sur le Nasdaq-100, les verts de 2000-2002 ont été suivis de nouvelles baisses (90e percentile de la baisse sur 24 mois : 61 %, contre 35 % après l'orange). Sa vraie valeur est de dire quand une réserve peut être engagée, en tranches.</p>"
            + plan_txt)


def _validation_summary() -> str:
    old = ""
    pv = DOCS_DIR.parent / "archive" / "backtest_summary_v0.6.json"
    if pv.exists():
        s = json.loads(pv.read_text(encoding="utf-8"))
        bits = []
        for a, name in (("sp500", "S&P 500"), ("ndx", "Nasdaq-100"), ("world", "MSCI World")):
            if a in s:
                g = s[a]["checks"]["écart_3ans_vert_moins_rouge"]
                bits.append(f"{name} {100 * g['valeur']:+.1f} pts {'✓' if g['ok'] else '✗'}")
        old = ("<div class='honest'><b>Règles v0.6 (archivées) :</b> écart vert − rouge à 3 ans " + " ; ".join(bits)
               + ". Critère pré-enregistré non atteint sur le S&P 500 et le MSCI World ; sommet de 2007 orange ; dette sur marge seule derrière 55 % "
               "des jours rouges du S&P 500 ; Bitcoin vert un tiers du temps. Ces échecs ont motivé le protocole v1.0.</div>")
    return ("<h3>1. Le test qui a fixé les règles v1.0</h3>" + _protocol_section()
            + "<h3>2. Les règles en vigueur, sur le passé (1990-2026 ; Bitcoin 2014-2026)</h3>" + _current_rules_section()
            + "<h3>3. Ce qu'il faut garder en tête</h3><div class='honest'><ul>"
            "<li>Le test 1990-2026 a servi à concevoir : il n'est pas hors échantillon. Seul 1920-1989 l'est, et seulement pour les indices.</li>"
            "<li>Les statistiques par couleur reposent sur quelques épisodes : des jours d'un même épisode ne sont pas des observations indépendantes.</li>"
            "<li>Le seul test qui ne dépend pas de ce que l'on sait du passé est l'avenir : les états du jour sont archivés chaque jour, avec leur empreinte, "
            "et seront confrontés aux rendements réalisés le 9 novembre 2027, 2028 et 2029.</li></ul></div>" + old)


def _glossary() -> str:
    items = "".join(f"<dt>{html.escape(t)}</dt><dd>{html.escape(d)}<span class='rule'>Dans les règles : {html.escape(rl)}</span></dd>" for t, d, rl in GLOSSARY)
    return f"<dl class='gloss'>{items}</dl>"


def _states(dfs: dict[str, pd.DataFrame]) -> dict:
    r = rules()
    st = {}
    for key, df in dfs.items():
        row = df.iloc[-1]
        st[key] = {"name": r["indices"]["assets"].get(key, {}).get("name", "Bitcoin"), "color": row["color_confirmed"],
                   "trend_broken": bool(row["trend_broken"]), "falling_knife": bool(row.get("falling_knife", False)),
                   "cher": bool(row.get("cher", False)), "cher_tendu": bool(row.get("cher_tendu", False)),
                   "V": None if pd.isna(row.get("V")) else float(row["V"]),
                   "er10": None if pd.isna(row.get("er10", float("nan"))) else float(row["er10"]),
                   "price": None if pd.isna(row.get("price")) else float(row["price"]),
                   "drawdown": None if pd.isna(row.get("drawdown")) else float(row["drawdown"]),
                   "date": str(df.index[-1].date())}
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
<h1>Feux tricolores <span class="toggle"><button data-m="simple">Mode simple</button><button data-m="detail">Mode détaillé</button></span></h1><p class="sub">Lecture générée le {now} · règles gelées le {r['frozen_at']} (v{r['version']}) · <a href="backtest.html">validation 1990-2026</a> · <a href="latest.json">données brutes</a></p>
<div class="warn">Un feu mesure un <b>état</b> (cher / tendu / euphorique, ou décoté / capitulation), pas une prévision. Il gouverne le levier, les montants exceptionnels et le rééquilibrage. Les versements réguliers ne s'arrêtent jamais, quelle que soit la couleur.</div>
<p class="headline">{html.escape(headline(states))}</p>
<div class="actions"><b>Ce mois-ci, concrètement</b><ul style="margin:6px 0 0;padding-left:18px">{acts}</ul></div>
<h2>Lecture du jour</h2><div class="grid">{''.join(cards)}</div>
<p class="legend"><i style="background:{HEX['green']}"></i>vert <i style="background:{HEX['orange']}"></i>orange <i style="background:{HEX['red']}"></i>rouge — frise mensuelle depuis 1990 (Bitcoin : 2014)</p>
{_themes_section()}
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
