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
from .themes import load_all as themes_all, simple_sentence

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
                                            "fcf_cagr_5y", "gap_ma200", "gap_ma200_pct", "runup_24m", "gsy", "trend_broken", "drawdown", "mom_12m", "date", "since",
                                            "source", "accounts_currency", "price_currency", "mode", "ebit_source", "shares_ok", "pe", "pb", "roe", "note")} | {"key": k})
    themes = []
    for k, df in themes_all().items():
        row = df.iloc[-1]
        themes.append({"key": k, "name": r["themes"]["assets"][k]["name"], "sentence": simple_sentence(k, row),
                       "runup_24m": float(row["runup_24m"]), "gsy": bool(row["gsy"]), "gap_ma200": float(row["gap_ma200"]),
                       "gap_pct": None if pd.isna(row["gap_ma200_pct"]) else float(row["gap_ma200_pct"]), "trend_broken": bool(row["trend_broken"]),
                       "drawdown": float(row["drawdown"]), "date": str(df.index[-1].date())})
    universe_as_of = None
    up = ROOT / "data" / "universe.csv"
    if up.exists():
        universe_as_of = str(pd.read_csv(up, nrows=1)["as_of"].iloc[0])
    return {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%d/%m/%Y %H:%M UTC"), "frozen_at": r["frozen_at"], "version": "0.4",
        "states": states, "headline": headline(states), "actions": monthly_actions(states), "base_rates": base,
        "stocks": rows, "universe_as_of": universe_as_of, "themes": themes,
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
{d._themes_section()}
<div class="warn" style="margin-top:18px">Un feu mesure un <b>état</b> (cher / tendu / euphorique, ou décoté / capitulation), pas une prévision. Il gouverne le levier, les montants exceptionnels et le rééquilibrage. Les versements réguliers ne s'arrêtent jamais.</div>
</section>

<section class="tab" id="tab-stocks">
<h2>Les 100 plus grandes capitalisations mondiales</h2>
<p class="sub">Univers = 100 premières pondérations du MSCI ACWI (positions publiées par l'ETF SPDR MSCI ACWI, au {html.escape(str(pay['universe_as_of']))}), une ligne par société, plus vos compléments de <code>stocks.yaml</code>.
Rouge = valorisation ≥ 80e percentile de son propre historique 10 ans ET (hausse ≥ 100 %/2 ans avec accélération OU écart MM200 ≥ 90e percentile) ; vert = valorisation ≤ 30e percentile ET filtre qualité réussi. Sans comptes (hors SEC), une société reste orange : seuls les drapeaux de prix sont calculés.</p>
<div id="stocks-notice"></div>
<div class="filters">
<input id="f-search" placeholder="Rechercher une société…">
<select id="f-color"><option value="">Toutes couleurs</option><option value="green">Vert</option><option value="orange">Orange</option><option value="red">Rouge</option></select>
<select id="f-country"><option value="">Tous pays</option></select>
<select id="f-sector"><option value="">Tous secteurs</option></select>
<label class="pill"><input type="checkbox" id="f-pea"> éligible PEA (approx.)</label>
<label class="pill"><input type="checkbox" id="f-gsy"> bulle GSY</label>
<label class="pill"><input type="checkbox" id="f-broken"> tendance cassée</label>
<label class="pill"><input type="checkbox" id="f-quality"> qualité OK</label>
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
<h2>Ce que les feux ont donné dans le passé (point-in-time)</h2>
{d._validation_summary()}
<details open><summary><b>Validation détaillée 1990-2026 : rendements par couleur, épisodes, coût des faux positifs, levier x2</b></summary>{_fragment('backtest')}</details>
<details><summary><b>Robustesse : sous-périodes, bootstrap, sensibilité des seuils, 1985-1989</b></summary>{_fragment('robustness')}</details>
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
const COLS=[['rank','#'],['name','Société'],['country','Pays'],['sector','Secteur'],['color_confirmed','Feu'],['V','Valorisation (p)'],['quality_ok','Qualité'],['implied_growth','Croissance implicite'],['gap_ma200','Écart MM200'],['runup_24m','Hausse 2 ans'],['gsy','Bulle GSY'],['trend_broken','Tendance'],['drawdown','Baisse vs plus haut'],['pea','PEA']];
function fmtCell(k,s){switch(k){
 case 'rank':return s.rank??'—';case 'name':return `<b>${s.name}</b><br><small>${s.ticker}</small>`;case 'color_confirmed':return `<span class="c ${s.color_confirmed}" style="font-weight:700">${LABEL[s.color_confirmed]||'—'}</span>`;
 case 'V':if(s.V==null)return s.kind!=='operating'?'<span class="note">prix seul</span>':(s.shares_ok===false?'<span class="note">n.d. (actions)</span>':'<span class="note">n.d. (historique)</span>');return `${Math.round(s.V)}<br><small>${s.mode==='financial'?`P/E ${num(s.pe)} · P/B ${num(s.pb,2)}`:`EV/EBIT ${num(s.ev_ebit)} · P/FCF ${num(s.p_fcf)}`}</small>`;
 case 'quality_ok':return s.V==null?'—':(s.quality_ok?'<span class="pill on">OK</span>':'<span class="pill" style="border-color:#b3261e;color:#b3261e">échec</span>')+(s.mode==='financial'?`<br><small>ROE ${pct(s.roe,0)}</small>`:'');
 case 'implied_growth':return s.implied_growth==null?'—':`${pct(s.implied_growth,0,true)}/an<br><small>réalisée 5 ans ${pct(s.fcf_cagr_5y,0,true)}</small>`;
 case 'gap_ma200':return `${pct(s.gap_ma200,0,true)}<br><small>p${s.gap_ma200_pct==null?'n.d.':Math.round(s.gap_ma200_pct)}</small>`;case 'runup_24m':return pct(s.runup_24m,0,true);
 case 'gsy':return s.gsy?'<b style="color:#b3261e">OUI</b>':'non';case 'trend_broken':return s.trend_broken?'<b style="color:#b3261e">cassée</b>':'OK';case 'drawdown':return pct(s.drawdown,0);
 case 'pea':return s.pea?'oui':'';default:return s[k]??'';}}
function filtered(){const q=($('#f-search').value||'').toLowerCase();const c=$('#f-color').value,co=$('#f-country').value,se=$('#f-sector').value;
 return S.filter(s=>(!q||(s.name+' '+s.ticker).toLowerCase().includes(q))&&(!c||s.color_confirmed===c)&&(!co||s.country===co)&&(!se||s.sector===se)&&(!$('#f-pea').checked||s.pea)&&(!$('#f-gsy').checked||s.gsy)&&(!$('#f-broken').checked||s.trend_broken)&&(!$('#f-quality').checked||s.quality_ok));}
function renderStocks(){const rows=filtered().sort((a,b)=>{let x=a[sortKey],y=b[sortKey];if(x==null)return 1;if(y==null)return -1;if(typeof x==='string')return sortAsc?x.localeCompare(y):y.localeCompare(x);return sortAsc?x-y:y-x;});
 $('#f-count').textContent=rows.length+' sociétés';
 $('#stocks-table').innerHTML='<tr>'+COLS.map(([k,l])=>`<th data-k="${k}" class="${k===sortKey?'sorted':''}">${l}</th>`).join('')+'</tr>'+rows.map(s=>`<tr class="row${s.color_confirmed}" data-key="${s.key}">${COLS.map(([k])=>`<td>${fmtCell(k,s)}</td>`).join('')}</tr>`).join('');
 $$('#stocks-table th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;if(sortKey===k)sortAsc=!sortAsc;else{sortKey=k;sortAsc=k==='name'||k==='country'||k==='sector'||k==='rank';}renderStocks();});
 $$('#stocks-table tr[data-key]').forEach(tr=>tr.onclick=()=>detail(tr.dataset.key));}
function detail(key){const s=S.find(x=>x.key===key);if(!s)return;const body=s.V==null?`<p>${s.kind!=='operating'?'Suivi en <b>prix seul</b> (pas de comptes dans EDGAR).':(s.shares_ok===false?'Comptes disponibles mais <b>nombre d\'actions incohérent</b> (actions multi-classes ou ADS) : valorisation non calculée plutôt que fausse.':'Comptes disponibles mais <b>historique trop court</b> (moins de cinq ans de ratios) : valorisation non calculée.')} Drapeaux : écart MM200 ${pct(s.gap_ma200,0,true)} (percentile ${s.gap_ma200_pct==null?'n.d.':Math.round(s.gap_ma200_pct)}), hausse 2 ans ${pct(s.runup_24m,0,true)}, bulle GSY ${s.gsy?'active':'non'}, tendance ${s.trend_broken?'cassée':'OK'}, ${pct(s.drawdown,0)} sous le plus haut.</p>`:
 (s.mode==='financial'?`<p><b>Valorisation (banque / assureur)</b> : P/E ${num(s.pe)} , P/B ${num(s.pb,2)} → V = ${Math.round(s.V)} (percentiles 10 ans de son propre historique). EV/EBIT et FCF n'ont pas de sens pour une banque.<br>
 <b>Qualité</b> : rentabilité des fonds propres ${pct(s.roe,0)} → ${s.quality_ok?'filtre réussi':'<b>filtre échoué</b> (jamais vert)'}.<br>`:
 `<p><b>Valorisation</b> : EV/EBIT ${num(s.ev_ebit)} (percentile 10 ans ${s.ev_ebit_pct==null?'n.d.':Math.round(s.ev_ebit_pct)}), P/FCF ${num(s.p_fcf)} (p${s.p_fcf_pct==null?'n.d.':Math.round(s.p_fcf_pct)}) → V = ${Math.round(s.V)}.${s.ebit_source&&s.ebit_source.indexOf('approximation')>=0?' <small>(résultat d\'exploitation non publié : approché par résultat avant impôt + intérêts)</small>':''}<br>
 <b>Qualité</b> : ROIC ${pct(s.roic,0)}, FCF/résultat net ${num(s.fcf_ni,2)}, dette nette/EBITDA ${num(s.nd_ebitda,1)} → ${s.quality_ok?'filtre réussi':'<b>filtre échoué</b> (jamais vert)'}.<br>
 <b>DCF inversé</b> : le cours suppose ${pct(s.implied_growth,0,true)}/an de croissance du cash pendant dix ans ; réalisé sur cinq ans : ${pct(s.fcf_cagr_5y,0,true)}/an.<br>`)+`
 <b>Prix</b> : écart MM200 ${pct(s.gap_ma200,0,true)}, hausse 2 ans ${pct(s.runup_24m,0,true)}, bulle GSY ${s.gsy?'active':'non'}, tendance ${s.trend_broken?'cassée':'OK'}, ${pct(s.drawdown,0)} sous le plus haut. Comptes en ${s.accounts_currency||'?'}, cours en ${s.price_currency||'?'}.</p>`;
 $('#stock-detail').innerHTML=`<div class="detail"><b>${s.name}</b> (${s.ticker}, ${s.country||'—'}, ${s.sector||'—'}) — feu <span class="c ${s.color_confirmed}" style="font-weight:700">${LABEL[s.color_confirmed]}</span> depuis le ${s.since||'—'} · données au ${s.date}${body}</div>`;$('#stock-detail').scrollIntoView({behavior:'smooth',block:'nearest'});}
['#f-search','#f-color','#f-country','#f-sector','#f-pea','#f-gsy','#f-broken','#f-quality'].forEach(id=>$(id).addEventListener('input',renderStocks));renderStocks();

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
