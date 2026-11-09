"""Application monopage (docs/index.html) : un seul fichier, autonome, publié par GitHub Pages.

Onglets : Aujourd'hui · Actions (Top 100) · Mon portefeuille · Journal · Validation · Règles & glossaire.
Les données du jour sont embarquées (window.FEUX) ; le portefeuille et le journal vivent dans le navigateur
(localStorage) : rien de personnel ne quitte l'appareil.
"""
from __future__ import annotations

import datetime as dt
import html
import json

import pandas as pd

from . import dashboard as d
from .config import DOCS_DIR, ROOT, rules
from .explain import conduct_text
from .plain import GLOSSARY, headline, monthly_actions
from .signals import load_signals
from .stocks import load_latest
from .themes import overlay as themes_overlay

APP_CSS = d.CSS + """
nav.tabs{display:flex;gap:4px;flex-wrap:wrap;border-bottom:1px solid var(--line);margin:14px 0 18px}
nav.tabs button{border:0;background:transparent;padding:10px 14px;font-size:15px;cursor:pointer;color:var(--muted);border-bottom:2px solid transparent;margin-bottom:-1px}
nav.tabs button.on{color:var(--ink);border-bottom-color:var(--ink);font-weight:600}
section.tab{display:none}section.tab.on{display:block}
.filters{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0 12px}.filters select,.filters input{padding:6px 8px;border:1px solid var(--line);border-radius:6px;font-size:14px;background:#fff}
table.stocks th{cursor:pointer;user-select:none;white-space:nowrap}table.stocks th.sorted::after{content:' ▾';color:var(--muted)}table.stocks td{white-space:nowrap}
.pill{display:inline-block;padding:1px 7px;border-radius:999px;font-size:12px;border:1px solid var(--line);color:var(--muted)}.pill.on{border-color:#1a7f37;color:#1a7f37}
.form{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;align-items:end;margin:10px 0}.form label{font-size:12px;color:var(--muted);display:flex;flex-direction:column;gap:3px}
.form input,.form select,.form textarea{padding:6px 8px;border:1px solid var(--line);border-radius:6px;font-size:14px;background:#fff}
button.btn{border:1px solid var(--ink);background:var(--ink);color:#fff;border-radius:6px;padding:7px 12px;cursor:pointer;font-size:14px}button.btn.ghost{background:#fff;color:var(--ink)}
button.btn[disabled]{opacity:.45;cursor:not-allowed}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:10px 0}
.kpi{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 12px}.kpi b{display:block;font-size:20px}.kpi span{font-size:12px;color:var(--muted)}
.bar{height:8px;background:#eee;border-radius:4px;overflow:hidden}.bar i{display:block;height:100%}.note{font-size:13px;color:var(--muted)}
.rowred td:first-child{border-left:3px solid var(--red)}.rowgreen td:first-child{border-left:3px solid var(--green)}
.detail{background:#f6f7f9;border-radius:8px;padding:10px 12px;font-size:13px;margin:6px 0 12px}
.vg{position:relative;height:6px;border-radius:3px;margin:4px 0 3px;min-width:90px;background:linear-gradient(90deg,#2e8b57 0%,#9acd32 30%,#f0c000 50%,#f08c00 70%,#b3261e 100%)}.vg i{position:absolute;top:-3px;width:3px;height:12px;margin-left:-1px;border-radius:2px;border:1px solid #fff}
small.warn{color:#b3261e}
.pill.warnp{border-color:#b3261e;color:#b3261e;background:#fff5f4}
.secs{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px}.sec{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 12px;border-left:4px solid var(--line)}
.sec.rowred{border-left-color:var(--red)}.sec.rowgreen{border-left-color:var(--green)}.sec.roworange{border-left-color:var(--orange)}
.sec-head{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.sec-flags{margin-left:auto;display:flex;gap:4px;flex-wrap:wrap}.sec-body{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:6px;font-size:13px}.sec-body>span:first-child{min-width:150px}
.dot{display:inline-block;width:12px;height:12px;border-radius:50%}.dot.green{background:var(--green)}.dot.orange{background:var(--orange)}.dot.red{background:var(--red)}
.sec-sentence{font-size:13px;margin:6px 0 0}.mems{margin:6px 0 0;font-size:12px}.mem{display:inline-block;padding:0 5px;border-radius:4px;border:1px solid var(--line);margin:1px 0}.mem.red{border-color:var(--red)}.mem.green{border-color:var(--green)}
@media (max-width:700px){.kv{grid-template-columns:1fr auto}table{font-size:12px}td,th{padding:5px}}
"""


def _payload() -> dict:
    r = rules()
    dfs = {k: load_signals(k) for k in list(r["indices"]["assets"]) + ["btc"]}
    states = d._states(dfs)
    # base rates par actif et couleur (pour le journal)
    base = {}
    p = DOCS_DIR / "backtest_summary.json"
    if p.exists():
        s = json.loads(p.read_text(encoding="utf-8"))
        for a in dfs:
            if a in s:
                base[a] = {}
                for c in ("green", "orange", "red"):
                    f1 = next((x for x in s[a]["fwd"] if x["horizon"] == "1 an" and x["couleur"] == c), None)
                    f3 = next((x for x in s[a]["fwd"] if x["horizon"] == "3 ans" and x["couleur"] == c), None)
                    dd = next((x for x in s[a]["dd24"] if x["couleur"] == c), None)
                    if f1 and f3 and dd:
                        base[a][c] = {"r1": f1["médiane_annualisée"], "neg1": f1["part_négative"], "r3": f3["médiane_annualisée"],
                                      "dd24": dd["drawdown_24m_médian"], "dd20": dd["part_drawdown_>20%"]}
    stocks = load_latest()
    rows = []
    for k, v in stocks.items():
        rows.append({kk: v.get(kk) for kk in ("name", "ticker", "country", "sector", "industry", "weight", "rank", "pea", "kind", "color_confirmed", "color",
                                            "V", "ev_ebit", "ev_ebit_pct", "p_fcf", "p_fcf_pct", "roic", "fcf_ni", "nd_ebitda", "quality_ok", "implied_growth",
                                            "roic_avg", "fcf_ni_avg", "nd_ebitda_avg", "roe_avg", "quality_fails", "quality_unknown", "da_known", "accounts_as_of", "shares_source",
                                            "fcf_cagr_5y", "gap_ma200", "gap_ma200_pct", "runup_24m", "gsy", "trend_broken", "drawdown", "mom_12m", "date", "since",
                                            "source", "accounts_currency", "price_currency", "mode", "ebit_source", "shares_ok", "pe", "pb", "roe", "note")} | {"key": k})
    themes = themes_overlay(stocks)
    q = r["stocks"]["quality"]
    # deux faits descriptifs sur l'univers réel (contexte, hors règles) : largeur et concentration
    priced = [s for s in rows if s.get("gap_ma200") is not None]
    breadth = {"n": len(priced), "above_ma200": sum(1 for s in priced if s["gap_ma200"] > 0),
               "trend_broken": sum(1 for s in priced if s.get("trend_broken")),
               "colors": {c: sum(1 for s in rows if s.get("color_confirmed") == c) for c in ("green", "orange", "red")}}
    try:
        from .universe import load as load_universe
        u = load_universe().sort_values("weight", ascending=False)
        tot = float(u["weight"].sum())
        breadth["top10_share"] = float(u["weight"].head(10).sum() / tot) if tot else None
        breadth["top1"] = {"name": str(u.iloc[0]["name"]), "share": float(u.iloc[0]["weight"] / tot)} if tot else None
    except Exception:
        breadth["top10_share"] = None
    universe_as_of = None
    up = ROOT / "data" / "universe.csv"
    if up.exists():
        universe_as_of = str(pd.read_csv(up, nrows=1)["as_of"].iloc[0])
    return {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%d/%m/%Y %H:%M UTC"), "generated_iso": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "frozen_at": r["frozen_at"], "version": str(r["version"]),
        "states": states, "headline": headline(states), "actions": monthly_actions(states), "base_rates": base,
        "stocks": rows, "universe_as_of": universe_as_of, "themes": themes, "breadth": breadth,
        "quality_rules": {"roic_min": q["roic_min"], "fcf_ni_min": q["fcf_to_net_income_min"], "nd_ebitda_max": q["net_debt_to_ebitda_max"],
                          "avg_years": q.get("avg_years", 5), "ebitda_avg_years": q.get("ebitda_avg_years", 3)},
        "stock_rules": {"red_min": r["stocks"]["valuation"]["red_min"], "green_max": r["stocks"]["valuation"]["green_max"],
                        "ext_red_min": r["stocks"]["extension"]["red_min"]},
        "conduct": {c: conduct_text(c) for c in ("green", "orange", "red")} | {"bands": {c: r["conduct"][c]["rebalance_band_pts"] for c in ("green", "orange", "red")},
                                                                          "lev_cap": {c: r["conduct"][c]["leverage_cap_share_equities"] for c in ("green", "orange", "red")},
                                                                          "lev_cap_broken": r["conduct"]["trend_broken"]["leverage_cap_share_equities"],
                                                                          "hours": r["conduct"]["exceptional_order_checklist_hours"]},
        "questions": ["Quelle couleur, et depuis quand ?", "Quel drapeau de tendance ?", "Le montant respecte-t-il le plafond de la couleur ?",
                      "Ai-je lu l'explication générée ?", "Agirais-je identiquement si le marché avait baissé de 10 % demain ?"],
    }


def _fragment(name: str) -> str:
    p = DOCS_DIR / "fragments" / f"{name}.html"
    return p.read_text(encoding="utf-8") if p.exists() else "<p class='sub'>Non généré.</p>"


def build() -> None:
    r = rules()
    pay = _payload()
    dfs = {k: load_signals(k) for k in r["indices"]["assets"]}
    cards = [d._card_index(k, r["indices"]["assets"][k]["name"], dfs[k]) for k in dfs]
    cards.append(d._card_btc(load_signals("btc")))
    acts = "".join(f"<li>{html.escape(a)}</li>" for a in pay["actions"])
    rules_yaml = html.escape((ROOT / "rules.yaml").read_text(encoding="utf-8"))
    page = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Feux tricolores</title><style>{APP_CSS}</style></head><body data-mode="simple"><main>
<h1>Feux tricolores <span class="toggle"><button data-m="simple">Mode simple</button><button data-m="detail">Mode détaillé</button></span></h1>
<p class="sub">Mise à jour {pay['generated']} · règles gelées le {pay['frozen_at']} · v{pay['version']}</p>
<nav class="tabs">
<button data-t="today" class="on">Aujourd'hui</button><button data-t="stocks">Actions · Top 100</button><button data-t="portfolio">Mon portefeuille</button>
<button data-t="journal">Journal</button><button data-t="validation">Validation</button><button data-t="rules">Règles &amp; glossaire</button></nav>

<section class="tab on" id="tab-today">
<p class="headline">{html.escape(pay['headline'])}</p>
<div class="actions"><b>Ce mois-ci, concrètement</b><ul style="margin:6px 0 0;padding-left:18px">{acts}</ul></div>
<h2>Lecture du jour</h2><div class="grid">{''.join(cards)}</div>
<p class="legend"><i style="background:{d.HEX['green']}"></i>vert <i style="background:{d.HEX['orange']}"></i>orange <i style="background:{d.HEX['red']}"></i>rouge — frise mensuelle depuis 1990 (Bitcoin : 2014)</p>
<h2>Secteurs et thèmes</h2>
<p class="sub">Les onze secteurs mondiaux et deux thèmes. Pour chaque secteur : les drapeaux de prix de son ETF (bulle, tension, tendance) et la valorisation médiane des sociétés du Top 100 qui le composent, combinées avec les mêmes règles que les indices (rouge = cher ET tendu ou en bulle ; vert = bon marché, ou capitulation). Lecture de contexte, non backtestée : elle ne gouverne ni le levier ni les montants.</p>
<div id="sectors"></div>
<div id="breadth" class="breadth"></div>
<div class="warn" style="margin-top:18px">Un feu mesure un <b>état</b> (cher / tendu / euphorique, ou décoté / capitulation), pas une prévision. Il gouverne le levier, les montants exceptionnels et le rééquilibrage. Les versements réguliers ne s'arrêtent jamais.</div>
</section>

<section class="tab" id="tab-stocks">
<h2>Les 100 plus grandes capitalisations mondiales</h2>
<p class="sub">Univers = 100 premières pondérations du MSCI ACWI (positions publiées par l'ETF SPDR MSCI ACWI, au {html.escape(str(pay['universe_as_of']))}), une ligne par société, plus vos compléments de <code>stocks.yaml</code>.
Le <b>feu</b> reste à trois couleurs et ne change que sur une conjonction : rouge = valorisation ≥ 80e percentile de son propre historique 10 ans <b>et</b> (hausse ≥ 100 %/2 ans avec accélération <b>ou</b> écart MM200 ≥ 90e percentile) ; vert = valorisation ≤ 30e percentile <b>et</b> société solide. Entre les deux, la <b>jauge de valorisation</b> (0 = la moins chère de sa propre histoire, 100 = la plus chère) et la <b>solidité</b> (rentabilité, cash, dette, en moyennes pluriannuelles) donnent le dégradé. Sans comptes (hors SEC), une société reste orange : seuls les drapeaux de prix sont calculés.</p>
<div id="stocks-summary" class="kpis"></div>
<div id="stocks-notice"></div>
<div class="filters">
<input id="f-search" placeholder="Rechercher une société…">
<select id="f-color"><option value="">Toutes couleurs</option><option value="green">Vert</option><option value="orange">Orange</option><option value="red">Rouge</option></select>
<select id="f-country"><option value="">Tous pays</option></select>
<select id="f-sector"><option value="">Tous secteurs</option></select>
<label class="pill"><input type="checkbox" id="f-pea"> éligible PEA (approx.)</label>
<label class="pill"><input type="checkbox" id="f-gsy"> bulle GSY</label>
<label class="pill"><input type="checkbox" id="f-broken"> tendance cassée</label>
<label class="pill"><input type="checkbox" id="f-quality"> solides seulement</label>
<select id="f-vband"><option value="">Toute valorisation</option><option value="0">très bon marché (≤ 20)</option><option value="20">bon marché (20-40)</option><option value="40">dans sa moyenne (40-60)</option><option value="60">cher (60-80)</option><option value="80">très cher (&gt; 80)</option></select>
<span class="note" id="f-count"></span></div>
<div style="overflow-x:auto"><table class="stocks" id="stocks-table"></table></div>
<div id="stock-detail"></div>
</section>

<section class="tab" id="tab-portfolio">
<h2>Mon portefeuille</h2>
<p class="sub">Saisissez vos lignes : elles restent dans ce navigateur (rien n'est envoyé). L'application calcule votre exposition réelle (le x2 compte double), la part en feu rouge, un test de résistance en euros, l'écart à vos cibles et où placer le prochain versement.</p>
<div class="form" id="pf-form">
<label>Libellé<input id="pf-label" placeholder="ETF Nasdaq-100 x2"></label>
<label>Sous-jacent<select id="pf-kind"><option value="ndx">Nasdaq-100</option><option value="sp500">S&amp;P 500</option><option value="world">MSCI World</option><option value="btc">Bitcoin / proxy</option><option value="stock">Action (Top 100 ou autre)</option><option value="other_equity">Autres actions / ETF</option><option value="safe">Sans risque (livret, fonds euros, monétaire, obligations)</option></select></label>
<label>Symbole (actions)<input id="pf-ticker" placeholder="ORCL, ASML.AS…"></label>
<label>Montant (€)<input id="pf-amount" type="number" min="0" step="100"></label>
<label>Levier<select id="pf-lev"><option value="1">×1</option><option value="2">×2</option><option value="3">×3</option></select></label>
<label>Enveloppe<select id="pf-acct"><option>PEA</option><option>CTO</option><option>Assurance-vie</option><option>Livret / cash</option><option>Autre</option></select></label>
<button class="btn" id="pf-add">Ajouter</button></div><p class="note" id="pf-msg" style="display:none"></p>
<div style="overflow-x:auto"><table id="pf-table"></table></div>
<h3>Cibles et versement</h3>
<div class="form" id="pf-targets">
<label>Cible actions indices &amp; monde (%)<input id="t-equity" type="number" value="60"></label>
<label>Cible actions individuelles (%)<input id="t-stock" type="number" value="15"></label>
<label>Cible Bitcoin &amp; proxys (%)<input id="t-btc" type="number" value="10"></label>
<label>Cible sans risque (%)<input id="t-safe" type="number" value="15"></label>
<label>Versement mensuel (€)<input id="t-monthly" type="number" value="1000"></label>
<button class="btn ghost" id="pf-save">Enregistrer</button>
<button class="btn ghost" id="pf-export">Copier (sauvegarde JSON)</button>
<label>Importer<input id="pf-import" type="file" accept="application/json"></label></div>
<div id="pf-export-box" style="display:none"><textarea style="width:100%;height:120px;font-size:12px"></textarea></div>
<div id="pf-analysis"></div>
</section>

<section class="tab" id="tab-journal">
<h2>Journal de décision</h2>
<p class="sub">Tout ordre exceptionnel commence par une intention écrite et cinq questions. La confirmation est impossible avant {pay['conduct']['hours']} heures. Les intentions restent dans ce navigateur (export possible).</p>
<div class="form">
<label>Actif<select id="j-asset"><option value="sp500">S&amp;P 500</option><option value="ndx">Nasdaq-100</option><option value="world">MSCI World</option><option value="btc">Bitcoin</option><option value="stock">Action (préciser)</option></select></label>
<label>Précision (symbole)<input id="j-ticker" placeholder="facultatif"></label>
<label>Action<select id="j-action"><option>acheter</option><option>vendre</option><option>arbitrer</option></select></label>
<label>Montant (€)<input id="j-amount" type="number" min="0" step="100"></label>
<label style="grid-column:1/-1">Thèse (pourquoi)<textarea id="j-thesis" rows="2"></textarea></label>
<label style="grid-column:1/-1">Ce qui invaliderait la décision<textarea id="j-inval" rows="2"></textarea></label>
<div id="j-questions" style="grid-column:1/-1"></div>
<div id="j-rates" class="detail" style="grid-column:1/-1"></div>
<button class="btn" id="j-add">Enregistrer l'intention</button><p class="note" id="j-add-msg" style="grid-column:1/-1;display:none"></p></div>
<div id="j-list"></div>
</section>

<section class="tab" id="tab-validation">
<h2>Ce que les feux valent vraiment (point-in-time)</h2>
{d._validation_summary()}
<details><summary><b>Détail 1990-2026 : rendements par couleur, dates clés, plan type, levier x2, sensibilité Bitcoin</b></summary>{_fragment('backtest')}</details>
<div id="sanity"></div>
<div id="prereg"></div>
</section>

<section class="tab" id="tab-rules">
<h2>Ce que chaque couleur autorise</h2>{d._conduct_table()}
<h2>Les mots et les chiffres, expliqués</h2>{d._glossary()}
<details><summary><b>Règles exactes (rules.yaml)</b></summary><pre style="font-size:12px;background:#f6f7f9;padding:10px;border-radius:8px;overflow:auto">{rules_yaml}</pre></details>
<footer>Sources : Robert Shiller (shillerdata.com) ; FRED (VIX, BAA10Y, TB3MS, séries Z.1) ; Yahoo Finance (prix) ; FINRA (dette sur marge) ; Coin Metrics Community (prix, MVRV, CC BY-NC 4.0) ; alternative.me (Fear &amp; Greed) ; Deribit (financement) ; State Street SPDR MSCI ACWI (positions) ; SEC EDGAR (comptes).
Outil personnel, déterministe, sans conseil en investissement.</footer>
</section>
</main>
<script>window.FEUX={json.dumps(pay, ensure_ascii=False, default=str)};</script>
<script>{APP_JS}</script>
{d.TOGGLE_JS}
</body></html>"""
    (DOCS_DIR / "index.html").write_text(page, encoding="utf-8")
    (DOCS_DIR / ".nojekyll").write_text("")


APP_JS = r"""
(function(){
const D=window.FEUX;const $=s=>document.querySelector(s);const $$=s=>Array.from(document.querySelectorAll(s));
const D_DATE=D.generated_iso||new Date().toISOString();const fmtDate=d=>{if(!d)return '';const x=new Date(d);return isNaN(x)?String(d):x.toLocaleDateString('fr-FR',{day:'2-digit',month:'2-digit',year:'numeric'});};
const LABEL={green:'VERT',orange:'ORANGE',red:'ROUGE'};const FR={green:'vert',orange:'orange',red:'rouge'};
const pct=(x,d=0,sign=false)=>x==null||isNaN(x)?'n.d.':((sign&&x>=0?'+':'')+(100*x).toFixed(d)+' %');
const num=(x,d=1)=>x==null||isNaN(x)?'n.d.':Number(x).toLocaleString('fr-FR',{maximumFractionDigits:d});
const eur=x=>Number(x||0).toLocaleString('fr-FR',{maximumFractionDigits:0})+' €';
function store(k,v){try{if(v===undefined)return JSON.parse(localStorage.getItem(k)||'null');localStorage.setItem(k,JSON.stringify(v));}catch(e){return null;}}
// ---- onglets (mémorisés) ----
function showTab(t){$$('nav.tabs button').forEach(b=>b.classList.toggle('on',b.dataset.t===t));$$('section.tab').forEach(s=>s.classList.toggle('on',s.id==='tab-'+t));store('feux-tab',t);}
const TABS=['today','stocks','portfolio','journal','validation','rules'];$$('nav.tabs button').forEach(b=>b.addEventListener('click',()=>{showTab(b.dataset.t);try{location.hash=b.dataset.t;}catch(e){}}));const h0=(location.hash||'').slice(1);showTab(TABS.includes(h0)?h0:(store('feux-tab')||'today'));window.addEventListener('hashchange',()=>{const h=(location.hash||'').slice(1);if(TABS.includes(h))showTab(h);});
function msg(id,text){const e=$(id);if(!e)return;e.textContent=text;e.style.display=text?'block':'none';}

// ---- Actions Top 100 ----
const S=D.stocks||[];let sortKey='rank',sortAsc=true;
const sel=(id,vals)=>{const e=$(id);vals.sort().forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;e.appendChild(o);});};
sel('#f-country',[...new Set(S.map(s=>s.country).filter(Boolean))]);sel('#f-sector',[...new Set(S.map(s=>s.sector).filter(Boolean))]);
const withAccounts=S.filter(s=>s.kind==='operating').length;
$('#stocks-notice').innerHTML=withAccounts?`<p class="note">${withAccounts} sociétés avec comptes SEC (valorisation et qualité calculées), ${S.length-withAccounts} en prix seul.</p>`:
 `<div class="warn">Comptes SEC non configurés : toutes les sociétés sont pour l'instant en <b>prix seul</b> (extension, bulle, tendance, baisse). Valorisation, qualité et DCF inversé apparaîtront dès que la variable <code>SEC_USER_AGENT</code> sera définie.</div>`;
const COLS=[['rank','#'],['name','Société'],['country','Pays'],['sector','Secteur'],['color_confirmed','Feu'],['V','Valorisation (0-100)'],['quality_ok','Solidité'],['implied_growth','Croissance implicite'],['gap_ma200','Écart MM200'],['runup_24m','Hausse 2 ans'],['gsy','Bulle GSY'],['trend_broken','Tendance'],['drawdown','Baisse vs plus haut'],['pea','PEA']];
const VLAB=v=>v==null?'n.d.':v<=20?'très bon marché':v<=40?'bon marché':v<=60?'dans sa moyenne':v<=80?'cher':'très cher';
const VHUE=v=>`hsl(${Math.round(120-1.2*Math.max(0,Math.min(100,v)))},60%,42%)`;
const vgauge=v=>v==null?'':`<div class="vg"><i style="left:${Math.max(0,Math.min(100,v))}%;background:${VHUE(v)}"></i></div>`;
const QR=D.quality_rules||{};const TESTS={rentabilité:s=>s.mode==='financial'?`rentabilité des fonds propres ${pct(s.roe_avg,0)} (seuil ${pct(QR.roic_min,0)})`:`rentabilité du capital ${pct(s.roic_avg,0)} (seuil ${pct(QR.roic_min,0)})`,cash:s=>`cash libre = ${num(s.fcf_ni_avg,2)} × résultat net (seuil ${num(QR.fcf_ni_min,2)})`,dette:s=>`dette nette = ${num(s.nd_ebitda_avg,1)} × EBITDA (seuil ${num(QR.nd_ebitda_max,1)})`};
const SHORT={rentabilité:s=>`rentabilité ${pct(s.mode==='financial'?s.roe_avg:s.roic_avg,0)}`,cash:s=>`cash ${num(s.fcf_ni_avg,2)}×`,dette:s=>`dette ${num(s.nd_ebitda_avg,1)}×`};
function solidity(s){if(s.V==null)return '—';if(s.mode==='reit')return '<span class="note">hors grille (foncière)</span>';const f=s.quality_fails||[],u=s.quality_unknown||[];
 if(s.quality_ok===true)return '<span class="pill on">solide</span>';
 if(!f.length&&u.length)return `<span class="note">n.d. (${u.join(', ')})</span>`;
 return f.map(k=>`<span class="pill warnp">⚠ ${SHORT[k](s)}</span>`).join(' ')+(u.length?`<br><small class="note">${u.join(', ')} : n.d.</small>`:'');}
function fmtCell(k,s){switch(k){
 case 'rank':return s.rank??'—';case 'name':return `<b>${s.name}</b><br><small>${s.ticker}</small>`;case 'color_confirmed':return `<span class="c ${s.color_confirmed}" style="font-weight:700">${LABEL[s.color_confirmed]||'—'}</span>`;
const ageMonths=d=>d?Math.round((new Date(D_DATE)-new Date(d))/2629800000):null;
const accountsNote=s=>{if(!s.accounts_as_of)return '';const m=ageMonths(s.accounts_as_of);const old=m!=null&&m>15;return `<br><small class="${old?'warn':'note'}">comptes au ${fmtDate(s.accounts_as_of)}${old?' — anciens ('+m+' mois) : lecture prudente':''}</small>`;};
 case 'V':if(s.V==null)return s.kind!=='operating'?'<span class="note">prix seul</span>':(s.shares_ok===false?'<span class="note">n.d. (actions)</span>':'<span class="note">n.d. (historique)</span>');return `<b>${Math.round(s.V)}</b> <small>${VLAB(s.V)}</small>${vgauge(s.V)}<small>${s.mode!=='industrial'?`P/E ${num(s.pe)} · P/B ${num(s.pb,2)}`:`EV/EBIT ${num(s.ev_ebit)} · P/FCF ${num(s.p_fcf)}`}</small>${accountsNote(s)}`;
 case 'quality_ok':return solidity(s);
 case 'implied_growth':return s.implied_growth==null?'—':`${pct(s.implied_growth,0,true)}/an<br><small>réalisée 5 ans ${pct(s.fcf_cagr_5y,0,true)}</small>`;
 case 'gap_ma200':return `${pct(s.gap_ma200,0,true)}<br><small>p${s.gap_ma200_pct==null?'n.d.':Math.round(s.gap_ma200_pct)}</small>`;case 'runup_24m':return pct(s.runup_24m,0,true);
 case 'gsy':return s.gsy?'<b style="color:#b3261e">OUI</b>':'non';case 'trend_broken':return s.trend_broken?'<b style="color:#b3261e">cassée</b>':'OK';case 'drawdown':return pct(s.drawdown,0);
 case 'pea':return s.pea?'oui':'';default:return s[k]??'';}}
function filtered(){const q=($('#f-search').value||'').toLowerCase();const c=$('#f-color').value,co=$('#f-country').value,se=$('#f-sector').value,vb=$('#f-vband').value;
 const inBand=s=>vb===''||(s.V!=null&&(vb==='80'?s.V>80:(s.V>+vb&&s.V<=+vb+20)||(vb==='0'&&s.V<=20)));
 return S.filter(s=>(!q||(s.name+' '+s.ticker).toLowerCase().includes(q))&&(!c||s.color_confirmed===c)&&(!co||s.country===co)&&(!se||s.sector===se)&&(!$('#f-pea').checked||s.pea)&&(!$('#f-gsy').checked||s.gsy)&&(!$('#f-broken').checked||s.trend_broken)&&(!$('#f-quality').checked||s.quality_ok===true)&&inBand(s));}
function summary(){const v=S.filter(s=>s.V!=null);const bands=[['≤ 20','très bon marché',s=>s.V<=20],['20-40','bon marché',s=>s.V>20&&s.V<=40],['40-60','dans sa moyenne',s=>s.V>40&&s.V<=60],['60-80','cher',s=>s.V>60&&s.V<=80],['> 80','très cher',s=>s.V>80]];
 const solid=v.filter(s=>s.quality_ok===true).length,reds=S.filter(s=>s.color_confirmed==='red').length,greens=S.filter(s=>s.color_confirmed==='green').length;
 $('#stocks-summary').innerHTML=bands.map(([r,l,f])=>{const n=v.filter(f).length;return `<div class="kpi" style="border-top:3px solid ${VHUE(r==='≤ 20'?10:r==='20-40'?30:r==='40-60'?50:r==='60-80'?70:90)}"><b>${n}</b><span>${l} (${r})</span></div>`;}).join('')+`<div class="kpi"><b>${solid}/${v.length}</b><span>solides (3 tests réussis)</span></div><div class="kpi"><b>${reds} · ${greens}</b><span>feux rouges · feux verts</span></div>`;}
summary();
function renderStocks(){const rows=filtered().sort((a,b)=>{let x=a[sortKey],y=b[sortKey];if(x==null)return 1;if(y==null)return -1;if(typeof x==='string')return sortAsc?x.localeCompare(y):y.localeCompare(x);return sortAsc?x-y:y-x;});
 $('#f-count').textContent=rows.length+' sociétés';
 $('#stocks-table').innerHTML='<tr>'+COLS.map(([k,l])=>`<th data-k="${k}" class="${k===sortKey?'sorted':''}">${l}</th>`).join('')+'</tr>'+rows.map(s=>`<tr class="row${s.color_confirmed}" data-key="${s.key}">${COLS.map(([k])=>`<td>${fmtCell(k,s)}</td>`).join('')}</tr>`).join('');
 $$('#stocks-table th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;if(sortKey===k)sortAsc=!sortAsc;else{sortKey=k;sortAsc=k==='name'||k==='country'||k==='sector'||k==='rank';}renderStocks();});
 $$('#stocks-table tr[data-key]').forEach(tr=>tr.onclick=()=>detail(tr.dataset.key));}
function detail(key){const s=S.find(x=>x.key===key);if(!s)return;const body=s.V==null?`<p>${s.kind!=='operating'?'Suivi en <b>prix seul</b> (pas de comptes dans EDGAR).':(s.shares_ok===false?'Comptes disponibles mais <b>nombre d\'actions incohérent</b> (actions multi-classes ou ADS) : valorisation non calculée plutôt que fausse.':'Comptes disponibles mais <b>historique trop court</b> (moins de cinq ans de ratios) : valorisation non calculée.')} Drapeaux : écart MM200 ${pct(s.gap_ma200,0,true)} (percentile ${s.gap_ma200_pct==null?'n.d.':Math.round(s.gap_ma200_pct)}), hausse 2 ans ${pct(s.runup_24m,0,true)}, bulle GSY ${s.gsy?'active':'non'}, tendance ${s.trend_broken?'cassée':'OK'}, ${pct(s.drawdown,0)} sous le plus haut.</p>`:
 (s.mode!=='industrial'?`<p><b>Valorisation (${s.mode==='reit'?'foncière':'banque / assureur'})</b> : P/E ${num(s.pe)} , P/B ${num(s.pb,2)} → V = ${Math.round(s.V)}, <b>${VLAB(s.V)}</b> par rapport à ses dix dernières années. EV/EBIT et FCF n'ont pas de sens ici.<br>
 <b>Solidité</b> : ${s.mode==='reit'?'la grille (rentabilité du capital, cash, dette/EBITDA) ne s\'applique pas à une foncière : pas de test, donc jamais verte.':`rentabilité des fonds propres ${pct(s.roe_avg,0)} en moyenne ${QR.avg_years} ans (dernier exercice ${pct(s.roe,0)}) → ${s.quality_ok===true?'solide':'<b>test échoué</b> (jamais vert)'}.`}<br>`:
 `<p><b>Valorisation</b> : EV/EBIT ${num(s.ev_ebit)} (percentile 10 ans ${s.ev_ebit_pct==null?'n.d.':Math.round(s.ev_ebit_pct)}), P/FCF ${num(s.p_fcf)} (p${s.p_fcf_pct==null?'n.d.':Math.round(s.p_fcf_pct)}) → V = ${Math.round(s.V)}, <b>${VLAB(s.V)}</b> par rapport à ses dix dernières années.${s.ebit_source&&s.ebit_source.indexOf('approximation')>=0?' <small>(résultat d\'exploitation non publié : approché par résultat avant impôt + intérêts)</small>':''}<br>
 <b>Solidité</b> (moyennes ${QR.avg_years} ans) : ${['rentabilité','cash','dette'].map(k=>{const ok=!(s.quality_fails||[]).includes(k),unk=(s.quality_unknown||[]).includes(k);return `${TESTS[k](s)} ${unk?'→ n.d.':ok?'✓':'<b>✗</b>'}`;}).join(' · ')} → ${s.quality_ok===true?'<b>solide</b>':(s.quality_fails||[]).length?'<b>test(s) échoué(s)</b> : jamais vert tant que cela dure':'incomplet'}.${s.da_known===0?' <small>(amortissements non publiés : EBITDA approché par le résultat d\'exploitation)</small>':''}<br>
 <small class="note">Dernier exercice glissant : rentabilité ${pct(s.roic,0)}, cash ${num(s.fcf_ni,2)}×, dette ${num(s.nd_ebitda,1)}×.</small><br>
 <b>DCF inversé</b> : le cours suppose ${pct(s.implied_growth,0,true)}/an de croissance du cash pendant dix ans ; réalisé sur cinq ans : ${pct(s.fcf_cagr_5y,0,true)}/an.<br>`)+`
 <b>Prix</b> : écart MM200 ${pct(s.gap_ma200,0,true)}, hausse 2 ans ${pct(s.runup_24m,0,true)}, bulle GSY ${s.gsy?'active':'non'}, tendance ${s.trend_broken?'cassée':'OK'}, ${pct(s.drawdown,0)} sous le plus haut. Comptes en ${s.accounts_currency||'?'}, cours en ${s.price_currency||'?'}.</p>`;
 $('#stock-detail').innerHTML=`<div class="detail"><b>${s.name}</b> (${s.ticker}, ${s.country||'—'}, ${s.sector||'—'}) — feu <span class="c ${s.color_confirmed}" style="font-weight:700">${LABEL[s.color_confirmed]}</span> depuis le ${s.since||'—'} · données au ${s.date}${body}</div>`;$('#stock-detail').scrollIntoView({behavior:'smooth',block:'nearest'});}
['#f-search','#f-color','#f-country','#f-sector','#f-pea','#f-gsy','#f-broken','#f-quality','#f-vband'].forEach(id=>$(id).addEventListener('input',renderStocks));renderStocks();

// ---- Secteurs et thèmes ----
function renderSectors(){const T=D.themes||[];if(!T.length){$('#sectors').innerHTML='<p class="note">Non calculé.</p>';return;}
 const flag=(on,txt)=>on?`<span class="pill warnp">${txt}</span>`:'';
 const row=t=>{const v=t.valuation||{};const med=v.v_median;const members=(v.members||[]).map(m=>`<span class="mem c ${m.color||'orange'}" title="${m.name}">${m.ticker}${m.V==null?'':' '+Math.round(m.V)}</span>`).join(' ');
  return `<div class="sec row${t.color}"><div class="sec-head"><span class="dot ${t.color}"></span><b>${t.name}</b> <small class="note">${t.ticker}${t.kind==='theme'?' · thème (drapeaux seulement)':''}</small>
  <span class="sec-flags">${flag(t.gsy,'bulle GSY')}${flag(t.extended,'tendu')}${flag(t.trend_broken,'tendance cassée')}${flag(t.drawdown>=0.25,`−${Math.round(100*t.drawdown)} % vs plus haut`)}</span></div>
  <div class="sec-body">${t.kind==='sector'?(med==null?`<span class="note">valorisation sectorielle n.d. (${v.n||0} société${(v.n||0)>1?'s':''} valorisée${(v.n||0)>1?'s':''}, minimum 3)</span>`:`<span><b>${Math.round(med)}</b> <small>${VLAB(med)} · médiane de ${v.n} sociétés</small>${vgauge(med)}</span>`):''}
  <span class="note">hausse 2 ans ${pct(t.runup_24m,0,true)} · écart MM200 ${pct(t.gap_ma200,0,true)}${t.gap_pct==null?'':' (p'+Math.round(t.gap_pct)+')'}</span></div>
  <p class="sec-sentence">${t.sentence}</p>${members?`<p class="detail-only mems">${members}</p>`:''}</div>`;};
 $('#sectors').innerHTML=`<div class="secs">${T.filter(t=>t.kind==='sector').map(row).join('')}</div><h3 style="margin:14px 0 6px">Thèmes</h3><div class="secs">${T.filter(t=>t.kind!=='sector').map(row).join('')}</div>`;}
renderSectors();
(function(){const b=D.breadth;if(!b||!b.n)return;const pct=(x,n)=>Math.round(100*x/n);
 $('#breadth').innerHTML=`<h3 style="margin:14px 0 6px">Le Top 100 en un coup d'œil <small class="note">(faits de contexte, hors règles)</small></h3>
 <p><b>${pct(b.above_ma200,b.n)} %</b> des ${b.n} plus grandes sociétés sont au-dessus de leur moyenne des 200 jours, <b>${pct(b.trend_broken,b.n)} %</b> ont une tendance cassée (dernier mois sous la moyenne 10 mois). Feux : <span class="c green">${b.colors.green} verts</span> · <span class="c orange">${b.colors.orange} orange</span> · <span class="c red">${b.colors.red} rouges</span>.${b.top10_share!=null?` Concentration : les 10 premières pèsent <b>${Math.round(100*b.top10_share)} %</b> du Top 100${b.top1?` (${b.top1.name} seule : ${Math.round(100*b.top1.share)} %)`:''}.`:''}</p>`;})();

// ---- Mon portefeuille ----
let PF=store('feux-portfolio')||{lines:[],targets:{equity:60,stock:15,btc:10,safe:15,monthly:1000}};
const stateOf=k=>D.states[k]||null;const stockOf=t=>S.find(s=>s.ticker&&t&&s.ticker.toUpperCase()===t.toUpperCase());
function lineColor(l){if(l.kind==='stock'){const s=stockOf(l.ticker);return s?s.color_confirmed:null;}if(l.kind==='other_equity')return (stateOf('world')||{}).color||null;if(l.kind==='safe')return null;return (stateOf(l.kind)||{}).color||null;}
function bucket(l){return l.kind==='safe'?'safe':l.kind==='btc'?'btc':l.kind==='stock'?'stock':'equity';}
function savePF(){store('feux-portfolio',PF);}
$('#pf-add').onclick=()=>{const amt=parseFloat($('#pf-amount').value);if(!(amt>0))return msg('#pf-msg','Indiquez un montant.');msg('#pf-msg','');PF.lines.push({label:$('#pf-label').value||$('#pf-kind').selectedOptions[0].text,kind:$('#pf-kind').value,ticker:$('#pf-ticker').value.trim(),amount:amt,lev:parseInt($('#pf-lev').value),acct:$('#pf-acct').value});savePF();renderPF();$('#pf-amount').value='';$('#pf-label').value='';$('#pf-ticker').value='';};
$('#pf-save').onclick=()=>{PF.targets={equity:+$('#t-equity').value,stock:+$('#t-stock').value,btc:+$('#t-btc').value,safe:+$('#t-safe').value,monthly:+$('#t-monthly').value};savePF();renderPF();};
$('#pf-export').onclick=async()=>{const txt=JSON.stringify(PF,null,1);$('#pf-export-box').style.display='block';$('#pf-export-box textarea').value=txt;try{await navigator.clipboard.writeText(txt);msg('#pf-msg','Copié dans le presse-papiers (et affiché ci-dessous).');}catch(e){msg('#pf-msg','Copiez le texte ci-dessous pour le sauvegarder.');}};
$('#pf-import').onchange=e=>{const f=e.target.files[0];if(!f)return;const r=new FileReader();r.onload=()=>{try{PF=JSON.parse(r.result);savePF();renderPF();msg('#pf-msg','Portefeuille importé.');}catch(err){msg('#pf-msg','Fichier invalide.');}};r.readAsText(f);};
function renderPF(){const t=PF.targets;['equity','stock','btc','safe','monthly'].forEach(k=>{const e=$('#t-'+k);if(e)e.value=t[k];});
 const L=PF.lines;const total=L.reduce((a,l)=>a+l.amount,0);
 $('#pf-table').innerHTML='<tr><th>Ligne</th><th>Sous-jacent</th><th>Enveloppe</th><th>Montant</th><th>Levier</th><th>Exposition réelle</th><th>Feu du sous-jacent</th><th></th></tr>'+L.map((l,i)=>{const c=lineColor(l);return `<tr class="row${c||''}"><td>${l.label}</td><td>${$('#pf-kind option[value="'+l.kind+'"]').textContent}${l.ticker?' · '+l.ticker:''}</td><td>${l.acct}</td><td>${eur(l.amount)}</td><td>×${l.lev}</td><td>${eur(l.amount*l.lev)}</td><td>${c?`<span class="c ${c}" style="font-weight:700">${LABEL[c]}</span>`:'—'}</td><td><button class="btn ghost" data-i="${i}">retirer</button></td></tr>`;}).join('')+(L.length?`<tr><th colspan="3">Total</th><th>${eur(total)}</th><th></th><th>${eur(L.reduce((a,l)=>a+l.amount*l.lev,0))}</th><th></th><th></th></tr>`:'');
 $$('#pf-table button').forEach(b=>b.onclick=()=>{PF.lines.splice(+b.dataset.i,1);savePF();renderPF();});
 if(!L.length){$('#pf-analysis').innerHTML='<p class="note">Ajoutez vos lignes pour obtenir l\'analyse.</p>';return;}
 const byB={equity:0,stock:0,btc:0,safe:0};L.forEach(l=>byB[bucket(l)]+=l.amount);const expo={equity:0,stock:0,btc:0,safe:0};L.forEach(l=>expo[bucket(l)]+=l.amount*l.lev);
 const red=L.filter(l=>lineColor(l)==='red').reduce((a,l)=>a+l.amount*l.lev,0);const green=L.filter(l=>lineColor(l)==='green').reduce((a,l)=>a+l.amount*l.lev,0);
 const eqExpo=expo.equity+expo.stock;const levExtra=L.filter(l=>bucket(l)!=='safe').reduce((a,l)=>a+l.amount*(l.lev-1),0);const levShare=eqExpo?levExtra/eqExpo:0;
 const worst=['red','orange','green'].find(c=>Object.keys(D.states).filter(k=>k!=='btc').some(k=>D.states[k].color===c))||'orange';const broken=Object.keys(D.states).filter(k=>k!=='btc').some(k=>D.states[k].trend_broken);
 const cap=broken?D.conduct.lev_cap_broken:D.conduct.lev_cap[worst];const band=D.conduct.bands[worst];
 const pea=L.filter(l=>l.acct==='PEA').reduce((a,l)=>a+l.amount,0),cto=L.filter(l=>l.acct==='CTO').reduce((a,l)=>a+l.amount,0);
 const tech=L.filter(l=>l.kind==='ndx'||(l.kind==='stock'&&(stockOf(l.ticker)||{}).sector&&/Information Technology|Communication/.test(stockOf(l.ticker).sector))).reduce((a,l)=>a+l.amount*l.lev,0);
 const shock=(sE,sB)=>L.reduce((a,l)=>{const b=bucket(l);if(b==='safe')return a;const s=b==='btc'?sB:sE;return a+Math.min(l.amount,l.amount*l.lev*s);},0);
 const kp=(v,lab)=>`<div class="kpi"><b>${v}</b><span>${lab}</span></div>`;
 let html=`<div class="kpis">${kp(eur(total),'patrimoine saisi')}${kp(eur(eqExpo+expo.btc),'exposition réelle au risque (levier compté)')}${kp(pct(total?red/total:0),'part exposée à un feu ROUGE')}${kp(pct(levShare),`part de levier dans la poche risquée (plafond actuel ${pct(cap)})`)}${kp(pct(total?tech/total:0),'exposition tech / Nasdaq (levier compté)')}${kp(pct(total?pea/total:0)+' / '+pct(total?cto/total:0),'PEA / CTO')}</div>`;
 html+=`<h3>Test de résistance (perte en euros, levier compté, perte plafonnée au montant investi)</h3><table><tr><th>Scénario</th><th>Actions −20 % · Bitcoin −40 %</th><th>Actions −40 % · Bitcoin −60 %</th><th>Actions −60 % · Bitcoin −80 %</th></tr><tr><td>Perte</td><td>−${eur(shock(.2,.4))}</td><td>−${eur(shock(.4,.6))}</td><td>−${eur(shock(.6,.8))}</td></tr><tr><td>Patrimoine restant</td><td>${eur(total-shock(.2,.4))}</td><td>${eur(total-shock(.4,.6))}</td><td>${eur(total-shock(.6,.8))}</td></tr></table>`;
 if(levShare>cap+1e-9)html+=`<div class="warn">Levier au-dessus du plafond de la couleur du jour (${pct(levShare)} > ${pct(cap)}) : ramener l'excédent vers l'ETF sans levier (dans le PEA, sans impôt).</div>`;
 const tg={equity:t.equity,stock:t.stock,btc:t.btc,safe:t.safe};const names={equity:'Actions indices & monde',stock:'Actions individuelles',btc:'Bitcoin & proxys',safe:'Sans risque'};
 html+=`<h3>Écart à vos cibles (bandes ±${band} points au feu ${FR[worst]})</h3><table><tr><th>Poche</th><th>Poids actuel</th><th>Cible</th><th>Écart</th><th>Feu</th><th></th></tr>`;
 const colorB={equity:worst,stock:null,btc:(stateOf('btc')||{}).color,safe:null};
 Object.keys(tg).forEach(b=>{const w=total?100*byB[b]/total:0;const gap=w-tg[b];const c=colorB[b];html+=`<tr><td>${names[b]}</td><td>${w.toFixed(0)} %</td><td>${tg[b]} %</td><td>${gap>=0?'+':''}${gap.toFixed(0)} pt${Math.abs(gap)>band?' <b style="color:#b3261e">hors bande</b>':''}</td><td>${c?`<span class="c ${c}" style="font-weight:700">${LABEL[c]}</span>`:'—'}</td><td><div class="bar"><i style="width:${Math.min(100,w)}%;background:${c==='red'?'#b3261e':c==='green'?'#1a7f37':'#c7641a'}"></i></div></td></tr>`;});
 html+='</table>';
 // prochain versement : poches sous la cible, hors rouge (le rouge n'arrête que les montants exceptionnels ; le versement régulier va d'abord aux poches sous-pondérées non rouges)
 const under=Object.keys(tg).map(b=>({b,gap:tg[b]-(total?100*byB[b]/total:0),c:colorB[b]})).filter(x=>x.gap>0);
 const elig=under.filter(x=>x.c!=='red');const pool=elig.length?elig:under;const sum=pool.reduce((a,x)=>a+x.gap,0);
 html+=`<h3>Où va le versement de ${eur(t.monthly)} ce mois-ci</h3><ul class="plain" style="padding-left:18px">`+(pool.length?pool.map(x=>`<li>${names[x.b]} : <b>${eur(t.monthly*x.gap/sum)}</b> (sous la cible de ${x.gap.toFixed(0)} pt${x.c==='red'?' — feu rouge : versement régulier seulement, aucun montant exceptionnel':''})</li>`).join(''):'<li>Toutes les poches sont à la cible : répartir selon les cibles.</li>')+'</ul>';
 if(elig.length&&under.length>elig.length)html+=`<p class="note">Les poches en feu rouge sous leur cible (${under.filter(x=>x.c==='red').map(x=>names[x.b]).join(', ')}) ne reçoivent pas le versement ce mois-ci tant qu'une autre poche est sous sa cible : on rééquilibre par les flux, sans vendre.</p>`;
 $('#pf-analysis').innerHTML=html;}
renderPF();

// ---- Journal ----
let J=store('feux-journal')||[];const Q=D.questions;
$('#j-questions').innerHTML=Q.map((q,i)=>`<label style="display:block;margin:4px 0;font-size:13px;color:var(--muted)">${q}<input data-q="${i}" style="width:100%;padding:6px 8px;border:1px solid var(--line);border-radius:6px"></label>`).join('');
function rates(){const a=$('#j-asset').value;const st=D.states[a];if(!st){$('#j-rates').textContent='Pour une action : voir sa fiche dans l\'onglet Actions.';return;}const br=(D.base_rates[a]||{})[st.color];
 $('#j-rates').innerHTML=`Feu <b>${LABEL[st.color]}</b> sur ${st.name}${st.trend_broken?' · tendance cassée':''}. `+(br?`Historiquement, après un jour ${FR[st.color]} : rendement médian <b>${pct(br.r1,1,true)}</b> à un an (négatif dans ${pct(br.neg1)} des cas), <b>${pct(br.r3,1,true)}/an</b> sur trois ans ; baisse médiane dans les 24 mois suivants <b>${pct(br.dd24)}</b> (plus de 20 % dans ${pct(br.dd20)} des cas).`:'');}
$('#j-asset').addEventListener('change',rates);rates();
function renderJ(){const now=Date.now();$('#j-list').innerHTML=J.length?'<h3>Intentions</h3>'+J.slice().reverse().map(it=>{const el=(now-new Date(it.created))/36e5;const ok=el>=D.conduct.hours;
 return `<div class="detail"><b>${new Date(it.created).toLocaleString('fr-FR')}</b> — ${it.action} ${it.assetName}${it.ticker?' ('+it.ticker+')':''} ${eur(it.amount)} · état : <b>${it.status}</b>${it.snapshot?` · feu à l'intention : ${LABEL[it.snapshot.color]||'—'}`:''}<br><i>Thèse :</i> ${it.thesis||'—'} · <i>Invalidation :</i> ${it.inval||'—'}<br>${it.rates?`<span class="note">${it.rates}</span><br>`:''}
 ${it.status==='en attente'?`<button class="btn" data-id="${it.id}" data-a="confirm" ${ok?'':'disabled'}>${ok?'Confirmer (les cinq questions sont redemandées)':'Confirmation possible dans '+Math.ceil(D.conduct.hours-el)+' h'}</button> <button class="btn ghost" data-id="${it.id}" data-a="cancel">Annuler</button><div class="confirm-box" data-for="${it.id}" style="display:none;margin-top:8px">${Q.map((q,i)=>`<label style="display:block;margin:4px 0;font-size:13px;color:var(--muted)">${q}<input data-cq="${i}" style="width:100%;padding:6px 8px;border:1px solid var(--line);border-radius:6px"></label>`).join('')}<button class="btn" data-id="${it.id}" data-a="confirm2">Valider la confirmation</button> <span class="note" data-cmsg="${it.id}"></span></div>`:''}</div>`;}).join('')+'<button class="btn ghost" id="j-export">Copier le journal (JSON)</button><div id="j-export-box" style="display:none"><textarea style="width:100%;height:120px;font-size:12px"></textarea></div><p class="note" id="j-msg"></p>':'<p class="note">Aucune intention enregistrée.</p>';
 $$('#j-list button[data-a]').forEach(b=>b.onclick=()=>{const it=J.find(x=>x.id===b.dataset.id);const a=b.dataset.a;
  if(a==='cancel'){it.status='annulé';store('feux-journal',J);renderJ();return;}
  if(a==='confirm'){const box=$(`.confirm-box[data-for="${it.id}"]`);box.style.display=box.style.display==='none'?'block':'none';return;}
  if(a==='confirm2'){const box=$(`.confirm-box[data-for="${it.id}"]`);const ans=Array.from(box.querySelectorAll('input[data-cq]')).map(i=>i.value.trim());if(ans.some(x=>!x)){box.querySelector('[data-cmsg]').textContent='Les cinq réponses sont obligatoires.';return;}it.status='confirmé';it.confirmed=new Date().toISOString();it.answers2=ans;store('feux-journal',J);renderJ();}});
 const ex=$('#j-export');if(ex)ex.onclick=async()=>{const txt=JSON.stringify(J,null,1);$('#j-export-box').style.display='block';$('#j-export-box textarea').value=txt;try{await navigator.clipboard.writeText(txt);msg('#j-msg','Copié dans le presse-papiers (et affiché ci-dessous).');}catch(e){msg('#j-msg','Copiez le texte ci-dessous pour le sauvegarder.');}};}
$('#j-add').onclick=()=>{const ans=$$('#j-questions input').map(i=>i.value.trim());if(ans.some(a=>!a))return msg('#j-add-msg','Répondez aux cinq questions avant d\'enregistrer.');msg('#j-add-msg','');const a=$('#j-asset').value;const st=D.states[a];
 J.push({id:Math.random().toString(36).slice(2,10),created:new Date().toISOString(),asset:a,assetName:st?st.name:'Action',ticker:$('#j-ticker').value.trim(),action:$('#j-action').value,amount:+$('#j-amount').value||0,thesis:$('#j-thesis').value,inval:$('#j-inval').value,answers:ans,snapshot:st?{color:st.color,trend_broken:st.trend_broken}:null,rates:$('#j-rates').textContent,status:'en attente'});
 store('feux-journal',J);$$('#j-questions input').forEach(i=>i.value='');$('#j-thesis').value='';$('#j-inval').value='';$('#j-amount').value='';renderJ();};
renderJ();
})();
"""
