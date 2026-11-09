"""Application monopage (docs/index.html) : un seul fichier, autonome, publié par GitHub Pages.

Onglets : Aujourd'hui · Actions (Top 100) · Mon portefeuille · Journal · Validation · Règles & glossaire.
Les données du jour sont embarquées (window.FEUX) ; le portefeuille et le journal vivent dans le navigateur
(localStorage) : rien de personnel ne quitte l'appareil.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import logging

import pandas as pd

from . import dashboard as d
from .config import DOCS_DIR, ROOT, rules
from .explain import conduct_text
from .plain import GLOSSARY, headline, monthly_actions
from .signals import load_signals
from .stocks import load_latest
from .themes import overlay as themes_overlay

log = logging.getLogger("feux.app")

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
.rowred td:first-child{border-left:3px solid var(--red)}.rowgreen td:first-child{border-left:3px solid var(--green)}.rownone td:first-child{border-left:3px dashed #9aa0a6}
.c.none{color:#6b7280}.dot.none{background:#d5d8dc;box-shadow:inset 0 0 0 2px #9aa0a6}.c.info{color:#4a6fa5}.dot.info{background:#4a6fa5}
.detail{background:#f6f7f9;border-radius:8px;padding:10px 12px;font-size:13px;margin:6px 0 12px}
.vg{position:relative;height:6px;border-radius:3px;margin:4px 0 3px;min-width:90px;background:linear-gradient(90deg,#2e8b57 0%,#9acd32 30%,#f0c000 50%,#f08c00 70%,#b3261e 100%)}.vg i{position:absolute;top:-3px;width:3px;height:12px;margin-left:-1px;border-radius:2px;border:1px solid #fff}
small.warn{color:#b3261e}.warnc{color:#b3261e}
.pill.warnp{border-color:#b3261e;color:#b3261e;background:#fff5f4}
.secs{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px}.sec{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 12px;border-left:4px solid var(--line)}
.sec.rowred{border-left-color:var(--red)}.sec.rowgreen{border-left-color:var(--green)}.sec.roworange{border-left-color:var(--orange)}.sec.rownone{border-left-color:#9aa0a6;border-left-style:dashed}.sec.rowinfo{border-left-color:#4a6fa5}.sec.flagged{border-left-color:#b3261e}
.sec-head{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.sec-flags{margin-left:auto;display:flex;gap:4px;flex-wrap:wrap}.sec-body{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:6px;font-size:13px}.sec-body>span:first-child{min-width:150px}
.dot{display:inline-block;width:12px;height:12px;border-radius:50%;background:#c9ccd1}.dot.green{background:var(--green)}.dot.orange{background:var(--orange)}.dot.red{background:var(--red)}
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
                                            "roic_avg", "fcf_ni_avg", "nd_ebitda_avg", "roe_avg", "quality_fails", "quality_unknown", "no_light_reason", "da_known", "accounts_as_of", "shares_source",
                                            "V_cross", "vs_sector", "sector_peers", "tendu", "stale_accounts", "fcf", "fcf_gross", "sbc", "sbc_known", "sbc_to_revenue",
                                            "shareholder_yield", "dividend_yield", "net_buyback_yield", "dilution_3y", "accruals", "gross_margin", "gross_profitability", "splits", "shares_cleaning",
                                            "fcf_cagr_5y", "gap_ma200", "gap_ma200_pct", "runup_24m", "gsy", "trend_broken", "drawdown", "mom_12m", "date", "since", "price",
                                            "source", "accounts_currency", "price_currency", "mode", "ebit_source", "shares_ok", "pe", "pb", "roe", "note",
                                            "debt", "debt_free", "ev", "mcap")} | {"key": k})
    themes = themes_overlay(stocks)
    q = r["stocks"]["quality"]
    # deux faits descriptifs sur l'univers réel (contexte, hors règles) : largeur et concentration
    priced = [s for s in rows if s.get("gap_ma200") is not None]
    breadth = {"n": len(priced), "above_ma200": sum(1 for s in priced if s["gap_ma200"] > 0),
               "trend_broken": sum(1 for s in priced if s.get("trend_broken")),
               "colors": {c: sum(1 for s in rows if s.get("color_confirmed") == c) for c in ("green", "orange", "red", "none")}}
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
        "stocks": rows, "universe_as_of": universe_as_of, "themes": themes, "breadth": breadth, "prereg": _prereg_rows(),
        "prereg_stocks": _prereg_stocks(),
        "quality_rules": {"roic_min": q["roic_min"], "fcf_ni_min": q["fcf_to_net_income_min"], "nd_ebitda_max": q["net_debt_to_ebitda_max"],
                          "avg_years": q.get("avg_years", 5), "ebitda_avg_years": q.get("ebitda_avg_years", 3)},
        "stock_rules": {"red_min": r["stocks"]["valuation"]["red_min"], "green_max": r["stocks"]["valuation"]["green_max"],
                        "ext_red_min": r["stocks"]["extension"]["red_min"]},
        "conduct": {c: conduct_text(c) for c in ("green", "orange", "red")} | {"bands": {c: r["conduct"][c]["rebalance_band_pts"] for c in ("green", "orange", "red")},
                                                                          "lev_cap": {c: r["conduct"][c]["leverage_cap_share_equities"] for c in ("green", "orange", "red")},
                                                                          "lev_cap_broken": r["conduct"]["trend_broken"]["leverage_cap_share_equities"],
                                                                          "hours": r["conduct"]["exceptional_order_checklist_hours"],
                                                                          "sell_cooling_days": r["conduct"].get("sell_cooling_days_in_stress", 7),
                                                                          "stress_drawdown": 0.20, "review_days": 90,
                                                                          "concentration_max": r["conduct"].get("concentration_max_single_stock", 0.12)},
        "checks": _checks(),
        "questions": ["Quelle couleur, et depuis quand ?", "Quel drapeau de tendance ?", "Le montant respecte-t-il le plafond de la couleur ?",
                      "Ai-je lu l'explication générée ?", "Agirais-je identiquement si le marché avait baissé de 10 % demain ?"],
    }


def _checks() -> dict:
    """Contrôles de publication et témoins du jour (python -m feux check), affichés dans l'onglet Validation."""
    p = DOCS_DIR / "checks.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        return {}


def _fragment(name: str) -> str:
    p = DOCS_DIR / "fragments" / f"{name}.html"
    return p.read_text(encoding="utf-8") if p.exists() else "<p class='sub'>Non généré.</p>"


def _prereg_stocks() -> list[dict]:
    try:
        from .prereg import stock_scores
        return stock_scores()
    except Exception as exc:   # pas bloquant
        log.warning("Suivi des pré-inscriptions (actions) indisponible : %s", exc)
        return []


def _prereg_rows() -> list[dict]:
    try:
        from .prereg import scoreboard
        return scoreboard()
    except Exception as exc:   # pas bloquant
        log.warning("Suivi des pré-inscriptions indisponible : %s", exc)
        return []


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
<p class="sub">Mise à jour {pay['generated']} <span id="fresh"></span> · règles gelées le {pay['frozen_at']} · v{pay['version']}</p>
<div id="stale-banner"></div>
<nav class="tabs">
<button data-t="today" class="on">Aujourd'hui</button><button data-t="stocks">Actions · Top 100</button><button data-t="portfolio">Mon portefeuille</button>
<button data-t="journal">Journal</button><button data-t="validation">Validation</button><button data-t="rules">Règles &amp; glossaire</button></nav>

<section class="tab on" id="tab-today">
<p class="headline">{html.escape(pay['headline'])}</p>
<div class="actions"><b>Ce mois-ci, concrètement</b><ul style="margin:6px 0 0;padding-left:18px">{acts}</ul></div>
<h2>Lecture du jour</h2><div class="grid">{''.join(cards)}</div>
<p class="legend"><i style="background:{d.HEX['green']}"></i>vert <i style="background:{d.HEX['orange']}"></i>orange <i style="background:{d.HEX['red']}"></i>rouge — frise mensuelle depuis 1990 (Bitcoin : 2014)</p>
<h2>Zones, secteurs et thèmes</h2>
<p class="sub"><b>Une information, pas un feu.</b> Chaque zone, secteur ou thème est situé contre <b>son propre passé</b> : très bon marché, bon marché, dans sa moyenne, cher, très cher. Comment : pour un secteur ou un thème comptant au moins 5 sociétés du Top 100, la médiane de leurs valorisations, chacune contre ses dix dernières années ; sinon, et pour les zones, le prix de l'ETF rapporté aux <b>dividendes</b> que ses sociétés ont versés en moyenne sur dix ans, inflation déduite (le même principe que le CAPE, avec les dividendes à la place des bénéfices, faute de bénéfices historiques gratuits par pays). <b>Pourquoi pas de feu :</b> testée sur 16 pays de 1870 à 2020, cette mesure a un peu distingué les marchés chers des marchés bon marché (années « bon marché » suivies de +1,9 point par an sur cinq ans, dans 13 pays sur 16), mais moins que le seuil de 2 points fixé avant le test ; la médiane des sociétés, elle, n'a pas d'historique pour être testée. Limites : une hausse du taux de distribution fait paraître une zone moins chère qu'elle ne l'est ; les dividendes des matières premières sont cycliques ; la comparaison porte sur 10 à 20 ans seulement. <b>Non mesurable</b> (gris) quand les données manquent : la raison est écrite. Les drapeaux de prix (bulle selon Greenwood, Shleifer et You, tension, tendance) complètent. Ni le levier ni les montants n'en dépendent.</p>
<div id="sectors"></div>
<div id="breadth" class="breadth"></div>
<div class="warn" style="margin-top:18px">Un feu mesure un <b>état</b> (cher / tendu / euphorique, ou décoté / capitulation), pas une prévision. Il gouverne le levier, les montants exceptionnels et le rééquilibrage. Les versements réguliers ne s'arrêtent jamais.</div>
</section>

<section class="tab" id="tab-stocks">
<h2>Les 100 plus grandes capitalisations mondiales</h2>
<p class="sub">Univers = 100 premières pondérations du MSCI ACWI (positions publiées par l'ETF SPDR MSCI ACWI, au {html.escape(str(pay['universe_as_of']))}), une ligne par société, plus vos compléments de <code>stocks.yaml</code>.
Chaque société est jugée sous <b>deux lentilles</b> : son prix contre <b>son propre passé</b> (EV/EBIT et P/FCF, percentile sur dix ans) et contre <b>les autres grandes sociétés</b> (rang de son multiple parmi les 100). Le flux de trésorerie est compté <b>après la rémunération en actions</b> des salariés, un coût réel. Le <b>feu est indicatif et non backtesté</b> : rouge seulement si la société est chère sous les deux lentilles <b>et</b> tendue (écart à la moyenne 200 jours au 90e percentile, ou hausse de 100 % en deux ans qui s'accélère) ; vert seulement si elle est bon marché sous les deux <b>et</b> solide (rentabilité, cash, dette, en moyennes sur cinq ans). Des comptes de plus de 15 mois laissent la société en orange. Sans comptes à la SEC, seuls les drapeaux de prix sont calculés.</p>
<div id="stocks-summary" class="kpis"></div>
<div id="stocks-notice"></div>
<div class="filters">
<input id="f-search" placeholder="Rechercher une société…">
<select id="f-color"><option value="">Toutes couleurs</option><option value="green">Vert</option><option value="orange">Orange</option><option value="red">Rouge</option><option value="none">Pas de feu (données insuffisantes)</option></select>
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
<p class="sub">Tout ordre exceptionnel commence par une intention écrite et cinq questions. La confirmation est impossible avant {pay['conduct']['hours']} heures ; pour une vente en période de stress (feu vert, couteau qui tombe, ou baisse de 20 % ou plus depuis le plus haut), avant {pay['conduct']['sell_cooling_days']} jours. Chaque décision confirmée revient {pay['conduct']['review_days']} jours plus tard pour une revue écrite. Les intentions restent dans ce navigateur (export possible).</p>
<div class="form">
<label>Actif<select id="j-asset"><option value="sp500">S&amp;P 500</option><option value="ndx">Nasdaq-100</option><option value="world">MSCI World</option><option value="btc">Bitcoin</option><option value="stock">Action (préciser)</option></select></label>
<label>Précision (symbole)<input id="j-ticker" placeholder="facultatif"></label>
<label>Action<select id="j-action"><option>acheter</option><option>vendre</option><option>arbitrer</option></select></label>
<label>Montant (€)<input id="j-amount" type="number" min="0" step="100"></label>
<label style="grid-column:1/-1">Thèse (pourquoi)<textarea id="j-thesis" rows="2"></textarea></label>
<label style="grid-column:1/-1">Ce qui invaliderait la décision<textarea id="j-inval" rows="2"></textarea></label>
<div id="j-questions" style="grid-column:1/-1"></div>
<div id="j-sell" class="detail" style="grid-column:1/-1;display:none"></div>
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
const LABEL={green:'VERT',orange:'ORANGE',red:'ROUGE',none:'PAS DE FEU'};const FR={green:'vert',orange:'orange',red:'rouge',none:'sans feu'};
const pct=(x,d=0,sign=false)=>x==null||isNaN(x)?'n.d.':((sign&&x>=0?'+':'')+(100*x).toFixed(d)+' %');
const num=(x,d=1)=>x==null||isNaN(x)?'n.d.':Number(x).toLocaleString('fr-FR',{maximumFractionDigits:d});
const eur=x=>Number(x||0).toLocaleString('fr-FR',{maximumFractionDigits:0})+' €';
function store(k,v){try{if(v===undefined)return JSON.parse(localStorage.getItem(k)||'null');localStorage.setItem(k,JSON.stringify(v));}catch(e){return null;}}
// ---- onglets (mémorisés) ----
function showTab(t){$$('nav.tabs button').forEach(b=>b.classList.toggle('on',b.dataset.t===t));$$('section.tab').forEach(s=>s.classList.toggle('on',s.id==='tab-'+t));store('feux-tab',t);}
const TABS=['today','stocks','portfolio','journal','validation','rules'];$$('nav.tabs button').forEach(b=>b.addEventListener('click',()=>{showTab(b.dataset.t);try{location.hash=b.dataset.t;}catch(e){}}));const h0=(location.hash||'').slice(1);showTab(TABS.includes(h0)?h0:(store('feux-tab')||'today'));window.addEventListener('hashchange',()=>{const h=(location.hash||'').slice(1);if(TABS.includes(h))showTab(h);});
function msg(id,text){const e=$(id);if(!e)return;e.textContent=text;e.style.display=text?'block':'none';}
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// ---- Actions Top 100 ----
const S=D.stocks||[];let sortKey='rank',sortAsc=true;
const sel=(id,vals)=>{const e=$(id);vals.sort().forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;e.appendChild(o);});};
sel('#f-country',[...new Set(S.map(s=>s.country).filter(Boolean))]);sel('#f-sector',[...new Set(S.map(s=>s.sector).filter(Boolean))]);
const withAccounts=S.filter(s=>s.kind==='operating').length;
$('#stocks-notice').innerHTML=withAccounts?`<p class="note">${withAccounts} sociétés avec comptes SEC (valorisation et qualité calculées), ${S.length-withAccounts} en prix seul.</p>`:
 `<div class="warn">Comptes SEC non configurés : toutes les sociétés sont pour l'instant en <b>prix seul</b> (extension, bulle, tendance, baisse). Valorisation, qualité et DCF inversé apparaîtront dès que la variable <code>SEC_USER_AGENT</code> sera définie.</div>`;
const COLS=[['rank','#'],['name','Société'],['color_confirmed','Feu (indicatif)'],['V','Valorisation vs son passé'],['V_cross','vs les 100'],['quality_ok','Solidité'],['shareholder_yield','Retour actionnaires'],['implied_growth','Croissance implicite'],['gap_ma200','Prix'],['pea','PEA']];
const VLAB=v=>v==null?'n.d.':v<=20?'très bon marché':v<=40?'bon marché':v<=60?'dans sa moyenne':v<=80?'cher':'très cher';
const VHUE=v=>`hsl(${Math.round(120-1.2*Math.max(0,Math.min(100,v)))},60%,42%)`;
const vgauge=v=>v==null?'':`<div class="vg"><i style="left:${Math.max(0,Math.min(100,v))}%;background:${VHUE(v)}"></i></div>`;
const QR=D.quality_rules||{};const TESTS={rentabilité:s=>s.mode==='financial'?`rentabilité des fonds propres ${pct(s.roe_avg,0)} (seuil ${pct(QR.roic_min,0)})`:`rentabilité du capital ${pct(s.roic_avg,0)} (seuil ${pct(QR.roic_min,0)})`,cash:s=>`cash libre net de la rémunération en actions = ${num(s.fcf_ni_avg,2)} × résultat net (seuil ${num(QR.fcf_ni_min,2)})`,dette:s=>`dette nette = ${num(s.nd_ebitda_avg,1)} × EBITDA (seuil ${num(QR.nd_ebitda_max,1)})`};
const SHORT={rentabilité:s=>`rentabilité ${pct(s.mode==='financial'?s.roe_avg:s.roic_avg,0)}`,cash:s=>`cash ${num(s.fcf_ni_avg,2)}×`,dette:s=>`dette ${num(s.nd_ebitda_avg,1)}×`};
function solidity(s){if(s.V==null)return '—';if(s.mode==='reit')return '<span class="note">hors grille (foncière)</span>';const f=s.quality_fails||[],u=s.quality_unknown||[];
 if(s.quality_ok===true)return '<span class="pill on">solide</span>';
 if(!f.length&&u.length)return `<span class="note">n.d. (${u.join(', ')})</span>`;
 return f.map(k=>`<span class="pill warnp">⚠ ${SHORT[k](s)}</span>`).join(' ')+(u.length?`<br><small class="note">${u.join(', ')} : n.d.</small>`:'');}
const ageMonths=d=>d?Math.round((new Date(D_DATE)-new Date(d))/2629800000):null;
const accountsNote=s=>{if(!s.accounts_as_of)return '';const m=ageMonths(s.accounts_as_of);const old=m!=null&&m>15;return `<br><small class="${old?'warn':'note'}">comptes au ${fmtDate(s.accounts_as_of)}${old?' — anciens ('+m+' mois) : lecture prudente':''}</small>`;};
function fmtCell(k,s){switch(k){
 case 'rank':return s.rank??'—';case 'name':return `<b>${s.name}</b><br><small>${s.ticker} · ${s.country||'—'} · ${s.sector||'—'}</small>`;case 'color_confirmed':return `<span class="c ${s.color_confirmed}" style="font-weight:700">${LABEL[s.color_confirmed]||'—'}</span>${s.color_confirmed==='none'&&s.no_light_reason?`<br><small class="note">${s.no_light_reason.split(' (')[0].split(' :')[0]}</small>`:''}`;
 case 'V_cross':if(s.V_cross==null)return '—';return `<b>${Math.round(s.V_cross)}</b>${vgauge(s.V_cross)}<small>${s.mode!=='industrial'?'P/E':'EV/EBIT'}${s.vs_sector!=null?` · secteur ${s.vs_sector>2?'> +200 %':pct(s.vs_sector,0,true)}`:''}</small>`;
 case 'shareholder_yield':return s.shareholder_yield==null?'—':`${pct(s.shareholder_yield,1)}<br><small>dividende ${pct(s.dividend_yield,1)} · actions ${s.dilution_3y==null?'n.d.':pct(s.dilution_3y,0,true)} en 3 ans</small>`;
 case 'V':if(s.V==null)return s.kind!=='operating'?'<span class="note">prix seul</span>':(s.shares_ok===false?'<span class="note">n.d. (actions)</span>':'<span class="note">n.d. (historique)</span>');return `<b>${Math.round(s.V)}</b> <small>${VLAB(s.V)}</small>${vgauge(s.V)}<small>${s.mode!=='industrial'?`P/E ${num(s.pe)} · P/B ${num(s.pb,2)}`:`EV/EBIT ${num(s.ev_ebit)} · P/FCF ${num(s.p_fcf)}`}</small>${accountsNote(s)}`;
 case 'quality_ok':return solidity(s);
 case 'implied_growth':return s.implied_growth==null?'—':`${pct(s.implied_growth,0,true)}/an<br><small>réalisée 5 ans ${pct(s.fcf_cagr_5y,0,true)}</small>`;
 case 'gap_ma200':return `${pct(s.gap_ma200,0,true)} vs MM200${s.tendu?' <b class="warnc">tendu</b>':''}<br><small>${s.trend_broken?'<b class="warnc">tendance cassée</b>':'tendance OK'} · ${pct(s.drawdown,0)} sous le plus haut${s.gsy?' · <b class="warnc">bulle GSY</b>':''}</small>`;case 'runup_24m':return pct(s.runup_24m,0,true);
 case 'gsy':return s.gsy?'<b style="color:#b3261e">OUI</b>':'non';case 'trend_broken':return s.trend_broken?'<b style="color:#b3261e">cassée</b>':'OK';case 'drawdown':return pct(s.drawdown,0);
 case 'pea':return s.pea?'oui':'';default:return s[k]??'';}}
function filtered(){const q=($('#f-search').value||'').toLowerCase();const c=$('#f-color').value,co=$('#f-country').value,se=$('#f-sector').value,vb=$('#f-vband').value;
 const inBand=s=>vb===''||(s.V!=null&&(vb==='80'?s.V>80:(s.V>+vb&&s.V<=+vb+20)||(vb==='0'&&s.V<=20)));
 return S.filter(s=>(!q||(s.name+' '+s.ticker).toLowerCase().includes(q))&&(!c||s.color_confirmed===c)&&(!co||s.country===co)&&(!se||s.sector===se)&&(!$('#f-pea').checked||s.pea)&&(!$('#f-gsy').checked||s.gsy)&&(!$('#f-broken').checked||s.trend_broken)&&(!$('#f-quality').checked||s.quality_ok===true)&&inBand(s));}
function summary(){const v=S.filter(s=>s.V!=null);const bands=[['≤ 20','très bon marché',s=>s.V<=20],['20-40','bon marché',s=>s.V>20&&s.V<=40],['40-60','dans sa moyenne',s=>s.V>40&&s.V<=60],['60-80','cher',s=>s.V>60&&s.V<=80],['> 80','très cher',s=>s.V>80]];
 const solid=v.filter(s=>s.quality_ok===true).length,reds=S.filter(s=>s.color_confirmed==='red').length,greens=S.filter(s=>s.color_confirmed==='green').length;
 $('#stocks-summary').innerHTML=bands.map(([r,l,f])=>{const n=v.filter(f).length;return `<div class="kpi" style="border-top:3px solid ${VHUE(r==='≤ 20'?10:r==='20-40'?30:r==='40-60'?50:r==='60-80'?70:90)}"><b>${n}</b><span>${l} (${r})</span></div>`;}).join('')+`<div class="kpi"><b>${solid}/${v.length}</b><span>solides (3 tests réussis)</span></div><div class="kpi"><b>${reds} · ${greens}</b><span>feux rouges · feux verts</span></div><div class="kpi" style="border-top:3px dashed #9aa0a6"><b>${S.filter(s=>s.color_confirmed==='none').length}</b><span>sans feu (données insuffisantes)</span></div>`;}
summary();
function renderStocks(){const rows=filtered().sort((a,b)=>{let x=a[sortKey],y=b[sortKey];if(x==null)return 1;if(y==null)return -1;if(typeof x==='string')return sortAsc?x.localeCompare(y):y.localeCompare(x);return sortAsc?x-y:y-x;});
 $('#f-count').textContent=rows.length+' sociétés';
 $('#stocks-table').innerHTML='<tr>'+COLS.map(([k,l])=>`<th data-k="${k}" class="${k===sortKey?'sorted':''}">${l}</th>`).join('')+'</tr>'+rows.map(s=>`<tr class="row${s.color_confirmed}" data-key="${s.key}">${COLS.map(([k])=>`<td>${fmtCell(k,s)}</td>`).join('')}</tr>`).join('');
 $$('#stocks-table th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;if(sortKey===k)sortAsc=!sortAsc;else{sortKey=k;sortAsc=k==='name'||k==='country'||k==='sector'||k==='rank';}renderStocks();});
 $$('#stocks-table tr[data-key]').forEach(tr=>tr.onclick=()=>detail(tr.dataset.key));}
function detail(key){const s=S.find(x=>x.key===key);if(!s)return;const body=s.V==null?`<p>${s.kind!=='operating'?'Suivi en <b>prix seul</b> (pas de comptes dans EDGAR).':(s.shares_ok===false?'Comptes disponibles mais <b>nombre d\'actions incohérent</b> (actions multi-classes ou ADS) : valorisation non calculée plutôt que fausse.':'Comptes disponibles mais <b>historique trop court</b> (moins de cinq ans de ratios) : valorisation non calculée.')} Drapeaux : écart MM200 ${pct(s.gap_ma200,0,true)} (percentile ${s.gap_ma200_pct==null?'n.d.':Math.round(s.gap_ma200_pct)}), hausse 2 ans ${pct(s.runup_24m,0,true)}, bulle GSY ${s.gsy?'active':'non'}, tendance ${s.trend_broken?'cassée':'OK'}, ${pct(s.drawdown,0)} sous le plus haut.</p>`:
 (s.mode!=='industrial'?`<p><b>Valorisation (${s.mode==='reit'?'foncière':'banque / assureur'})</b> : P/E ${num(s.pe)} , P/B ${num(s.pb,2)} → V = ${Math.round(s.V)}, <b>${VLAB(s.V)}</b> par rapport à ses dix dernières années. EV/EBIT et FCF n'ont pas de sens ici.<br>
 <b>Solidité</b> : ${s.mode==='reit'?'la grille (rentabilité du capital, cash, dette/EBITDA) ne s\'applique pas à une foncière : pas de test, donc jamais verte.':`rentabilité des fonds propres ${pct(s.roe_avg,0)} en moyenne ${QR.avg_years} ans (dernier exercice ${pct(s.roe,0)}) → ${s.quality_ok===true?'solide':'<b>test échoué</b> (jamais vert)'}.`}<br>`:
 `<p><b>Valorisation, lentille 1 (son propre passé)</b> : EV/EBIT ${num(s.ev_ebit)} (percentile 10 ans ${s.ev_ebit_pct==null?'n.d.':Math.round(s.ev_ebit_pct)}), P/FCF ${num(s.p_fcf)} (p${s.p_fcf_pct==null?'n.d.':Math.round(s.p_fcf_pct)}) → V = ${Math.round(s.V)}, <b>${VLAB(s.V)}</b> par rapport à ses dix dernières années.${s.ebit_source&&s.ebit_source.indexOf('approximation')>=0?' <small>(résultat d\'exploitation non publié : approché par résultat avant impôt + intérêts)</small>':''}<br>
 <b>Lentille 2 (les autres)</b> : ${s.V_cross==null?'n.d.':`plus cher que ${Math.round(s.V_cross)} % des grandes sociétés comparables`}${s.vs_sector!=null?` ; ${s.vs_sector>=0?'prime':'décote'} de ${Math.abs(Math.round(100*s.vs_sector))} % sur la médiane de son secteur (${s.sector_peers} sociétés)`:''}. Une société peut être bon marché contre son passé et chère contre les autres (multiple en baisse après une forte croissance), ou l'inverse : le feu exige l'accord des deux.<br>
 <b>Dette financière</b> : ${s.debt_free?'aucune dette déclarée (et intérêts négligeables) : comptée nulle':s.debt==null?'<b>inconnue</b> (concepts XBRL non reconnus) : ni valeur d\'entreprise, ni test de dette — jamais comptée nulle':num(s.debt/1e9,1)+' Md, part à moins d\'un an comprise'}.<br>
 <b>Cash</b> : flux libre ${s.fcf_gross==null?'n.d.':num(s.fcf_gross/1e9,1)+' Md'} avant rémunération en actions, <b>${s.fcf==null?'n.d.':num(s.fcf/1e9,1)+' Md'}</b> après${s.sbc_to_revenue!=null?` (rémunération en actions : ${pct(s.sbc_to_revenue,1)} du chiffre d'affaires)`:s.sbc_known===false?' (rémunération en actions non publiée : comptée à zéro)':''} ; c'est ce flux net qui sert au P/FCF, au test de cash et au DCF inversé.<br>
 <b>Retour aux actionnaires (12 mois)</b> : ${pct(s.shareholder_yield,1)} de la capitalisation (dividendes ${pct(s.dividend_yield,1)}, rachats nets ${pct(s.net_buyback_yield,1)}) ; nombre d'actions ${s.dilution_3y==null?'n.d.':pct(s.dilution_3y,0,true)} en trois ans${s.splits&&s.splits.length?` (divisions d'actions prises en compte : ${s.splits.map(x=>x[0]+' ×'+x[1]).join(', ')})`:''}${s.shares_cleaning&&(s.shares_cleaning.scale_fixed||s.shares_cleaning.dropped)?` ; données SEC nettoyées : ${s.shares_cleaning.scale_fixed||0} nombre(s) d'actions publié(s) en milliers ou millions corrigé(s), ${s.shares_cleaning.dropped||0} aberrant(s) écarté(s)`:''}.<br>
 <b>Qualité des résultats</b> : marge brute ${pct(s.gross_margin,0)} ; écart résultat − cash d'exploitation ${pct(s.accruals,1,true)} de l'actif (positif et élevé = bénéfices peu convertis en cash, Sloan 1996).<br>
 <b>Solidité</b> (moyennes ${QR.avg_years} ans) : ${['rentabilité','cash','dette'].map(k=>{const ok=!(s.quality_fails||[]).includes(k),unk=(s.quality_unknown||[]).includes(k);return `${TESTS[k](s)} ${unk?'→ n.d.':ok?'✓':'<b>✗</b>'}`;}).join(' · ')} → ${s.quality_ok===true?'<b>solide</b>':(s.quality_fails||[]).length?'<b>test(s) échoué(s)</b> : jamais vert tant que cela dure':'incomplet'}.${s.da_known===0?' <small>(amortissements non publiés : EBITDA approché par le résultat d\'exploitation)</small>':''}<br>
 <small class="note">Dernier exercice glissant : rentabilité ${pct(s.roic,0)}, cash ${num(s.fcf_ni,2)}×, dette ${num(s.nd_ebitda,1)}×.</small><br>
 <b>DCF inversé</b> : le cours suppose ${pct(s.implied_growth,0,true)}/an de croissance du cash pendant dix ans ; réalisé sur cinq ans : ${pct(s.fcf_cagr_5y,0,true)}/an.<br>`)+`
 <b>Prix</b> : écart MM200 ${pct(s.gap_ma200,0,true)}, hausse 2 ans ${pct(s.runup_24m,0,true)}, bulle GSY ${s.gsy?'active':'non'}, tendance ${s.trend_broken?'cassée':'OK'}, ${pct(s.drawdown,0)} sous le plus haut. Comptes en ${s.accounts_currency||'?'}, cours en ${s.price_currency||'?'}.</p>`;
 $('#stock-detail').innerHTML=`<div class="detail"><b>${s.name}</b> (${s.ticker}, ${s.country||'—'}, ${s.sector||'—'}) — feu <span class="c ${s.color_confirmed}" style="font-weight:700">${LABEL[s.color_confirmed]}</span> depuis le ${s.since||'—'} · cours au ${fmtDate(s.date)}${s.accounts_as_of?` · comptes au ${fmtDate(s.accounts_as_of)}`:''}${s.color_confirmed==='none'?`<div class="warn" style="margin-top:6px"><b>Pas de feu</b> : ${s.no_light_reason||'données insuffisantes'}. Aucune couleur n'est affichée plutôt qu'un orange par défaut.</div>`:''}${body}</div>`;$('#stock-detail').scrollIntoView({behavior:'smooth',block:'nearest'});}
['#f-search','#f-color','#f-country','#f-sector','#f-pea','#f-gsy','#f-broken','#f-quality','#f-vband'].forEach(id=>$(id).addEventListener('input',renderStocks));renderStocks();

// ---- Secteurs et thèmes ----
function renderSectors(){const T=D.themes||[];if(!T.length){$('#sectors').innerHTML='<p class="note">Non calculé.</p>';return;}
 const flag=(on,txt)=>on?`<span class="pill warnp">${txt}</span>`:'';
 const ORD={info:0,green:0,orange:1,red:1,none:2};
 const row=t=>{const L=t.light||{color_confirmed:'none'};const c=L.color_confirmed||'none';const v=t.valuation||{};
  const members=(v.members||[]).map(m=>`<span class="mem c ${m.color||'none'}" title="${esc(m.name)}">${esc(m.ticker)}${m.V==null?'':' '+Math.round(m.V)}</span>`).join(' ');
  const val=c==='none'?`<span class="note"><b>Valorisation non mesurable</b> : ${esc(L.reason||'données insuffisantes')}.</span>`
   :`<span><b>${Math.round(L.V)}</b> <small>${VLAB(L.V)} contre son passé · depuis le ${fmtDate(L.since)}</small>${vgauge(L.V)}</span><span class="note detail-only">${esc(L.measure||'')}</span>`;
  const tag=c==='info'?VLAB(L.V).toUpperCase():c==='none'?'NON MESURABLE':LABEL[c];
  return `<div class="sec row${c}"><div class="sec-head"><span class="dot ${c}"></span><b>${esc(t.name)}</b> <small class="note">${esc(t.ticker)} · ${fmtDate(t.date)}</small>
  <span class="c ${c}" style="font-weight:700;margin-left:6px">${tag}</span>
  <span class="sec-flags">${flag(t.gsy,'bulle GSY')}${flag(t.extended,'tendu')}${flag(t.trend_broken,'tendance cassée')}${flag(t.drawdown>=0.25,`−${Math.round(100*t.drawdown)} % vs plus haut`)}</span></div>
  <div class="sec-body">${val}<span class="note">hausse 2 ans ${pct(t.runup_24m,0,true)} · écart MM200 ${pct(t.gap_ma200,0,true)}${t.avg_yield_10y==null?'':' · dividendes moyens 10 ans '+pct(t.avg_yield_10y,1)}</span></div>
  <p class="sec-sentence">${t.sentence}</p>${members?`<p class="detail-only mems">${members}</p>`:''}</div>`;};
 const sort=(a,b)=>(ORD[(a.light||{}).color_confirmed||'none']-ORD[(b.light||{}).color_confirmed||'none'])||(((a.light||{}).V??999)-((b.light||{}).V??999));
 const group=(kind,title)=>{const G=T.filter(t=>t.kind===kind).sort(sort);if(!G.length)return '';
  const cnt=f=>G.filter(t=>{const L=t.light||{};return L.color_confirmed==='info'&&L.V!=null&&f(L.V);}).length;const nn=G.filter(t=>((t.light||{}).color_confirmed||'none')==='none').length;
  return `<h3 style="margin:14px 0 6px">${title} <small class="note">${cnt(v=>v<=40)} bon marché · ${cnt(v=>v>40&&v<80)} dans la moyenne ou un peu chers · ${cnt(v=>v>=80)} cher${cnt(v=>v>=80)>1?'s':''} · ${nn} non mesurable${nn>1?'s':''}</small></h3><div class="secs">${G.map(row).join('')}</div>`;};
 $('#sectors').innerHTML=group('zone','Zones et pays')+group('sector','Les onze secteurs')+group('theme','Thèmes');}
renderSectors();
(function(){const P=D.prereg||[];const el=$('#prereg');if(!el)return;
 if(!P.length){el.innerHTML='';return;}
 const by={};P.forEach(r=>{const k=r.date+(r.amendement?' '+r.amendement:'');(by[k]=by[k]||[]).push(r);});
 el.innerHTML=`<h3>5. Le vrai test : l'avenir (pré-inscriptions)</h3><p class="note">Chaque mois, l'état de chaque actif et ce que l'histoire « promet » pour sa couleur sont inscrits, hachés (SHA-256) et commités ; ils seront confrontés au réalisé à un an et à trois ans. Rien d'inscrit n'est modifié ensuite.</p>`+
 Object.keys(by).sort().reverse().map(d=>`<table><tr><th>Inscrit le ${fmtDate(by[d][0].date)}${by[d][0].amendement?` — amendement ${esc(by[d][0].amendement)} (règles v${esc(by[d][0].règles||'')})`:(by[d][0].règles?` — règles v${esc(by[d][0].règles)}`:'')} <small>(empreinte ${by[d][0].empreinte}… ${by[d][0].empreinte_ok?'✓ recalculée identique':'<b class="warnc">✗ ne correspond plus au fichier</b>'})</small></th><th>Couleur</th><th>Promesse historique à 1 an (médiane)</th><th>Réalisé 1 an</th><th>Promesse à 3 ans (médiane/an)</th><th>Réalisé 3 ans</th></tr>`+
 by[d].map(r=>{const a=r.attentes||{};const m1=a['1 an']?a['1 an'].médiane:null,m3=a['3 ans']?a['3 ans'].médiane:null;
  return `<tr><td>${({sp500:'S&P 500',ndx:'Nasdaq-100',world:'MSCI World',btc:'Bitcoin'})[r.actif]||r.actif}</td><td class="c ${r.couleur}">${LABEL[r.couleur]||r.couleur}${r.cher?' · cher':''}</td><td>${m1==null?'—':pct(m1,1,true)}</td><td>${r['1 an']==null?'<span class="note">à venir</span>':pct(r['1 an'],1,true)}</td><td>${m3==null?'—':pct(m3,1,true)}</td><td>${r['3 ans']==null?'<span class="note">à venir</span>':pct(r['3 ans'],1,true)}</td></tr>`;}).join('')+'</table>').join('')
 +((D.prereg_stocks||[]).length?`<p class="note" style="margin-top:10px"><b>Actions (feu indicatif)</b> : rendement médian réalisé, en devise de cotation, depuis le prix inscrit.</p><table><tr><th>Inscrit le</th><th>Groupe (effectif)</th><th>1 an</th><th>3 ans</th></tr>`+
   D.prereg_stocks.map(r=>['vertes','rouges','solides','non solides'].map((g,i)=>`<tr><td>${i?'':fmtDate(r.date)}</td><td>${g} (${(r.effectifs||{})[g]??0})</td><td>${r['1 an']&&r['1 an'][g]!=null?pct(r['1 an'][g],1,true):'<span class="note">à venir</span>'}</td><td>${r['3 ans']&&r['3 ans'][g]!=null?pct(r['3 ans'][g],1,true):'<span class="note">à venir</span>'}</td></tr>`).join('')).join('')+'</table>':'');})();
(function(){const b=D.breadth;if(!b||!b.n)return;const pct=(x,n)=>Math.round(100*x/n);
 $('#breadth').innerHTML=`<h3 style="margin:14px 0 6px">Le Top 100 en un coup d'œil <small class="note">(faits de contexte, hors règles)</small></h3>
 <p><b>${pct(b.above_ma200,b.n)} %</b> des ${b.n} plus grandes sociétés sont au-dessus de leur moyenne des 200 jours, <b>${pct(b.trend_broken,b.n)} %</b> ont une tendance cassée (dernier mois sous la moyenne 10 mois). Feux : <span class="c green">${b.colors.green} verts</span> · <span class="c orange">${b.colors.orange} orange</span> · <span class="c red">${b.colors.red} rouges</span>.${b.top10_share!=null?` Concentration : les 10 premières pèsent <b>${Math.round(100*b.top10_share)} %</b> du Top 100${b.top1?` (${b.top1.name} seule : ${Math.round(100*b.top1.share)} %)`:''}.`:''}</p>`;})();

// ---- Fraîcheur et témoins ----
(function(){const h=(Date.now()-new Date(D.generated_iso))/36e5;const el=$('#fresh');if(el&&!isNaN(h))el.textContent=`(il y a ${h<1?'moins d\u2019une heure':h<48?Math.round(h)+' h':Math.round(h/24)+' jours'})`;
 if(h>96)$('#stale-banner').innerHTML=`<div class="warn">Données vieilles de ${Math.round(h/24)} jours : la mise à jour automatique a probablement été arrêtée par un contrôle (le site garde alors la dernière version sûre). Voir l'onglet Validation et l'onglet « Actions » du dépôt GitHub.</div>`;})();
(function(){const C=D.checks||{};const el=$('#sanity');if(!el||!C.publication)return;
 const all=[...(C.publication||[]),...(C['témoins']||[])];const nko=all.filter(x=>!x.ok).length;
 const wit=(C['témoins']||[]).map(w=>`<tr><td>${w['témoin']}${w.critique?' <small class="note">(bloquant)</small>':''}</td><td>${w.attendu}</td><td>${w['observé']}</td><td class="${w.ok?'ok':'ko'}">${w.ok?'OK':'ÉCHEC'}</td></tr>`).join('');
 const pub=(C.publication||[]).map(c=>`<tr><td>${c['contrôle']}${c.bloquant===false?' <small class="note">(non bloquant)</small>':''}</td><td>${c['observé']??'—'}</td><td class="${c.ok?'ok':'ko'}">${c.ok?'OK':'ÉCHEC'}</td></tr>`).join('');
 el.innerHTML=`<h3>4. Témoins : ce que le code doit faire, vérifié avant chaque publication</h3><p class="note">Avant de publier, des contrôles vérifient que les données sont fraîches et complètes, et des « témoins » que les règles se comportent comme annoncé sur les données du jour (repris de Kairys). Un contrôle bloquant en échec arrête la mise à jour : le site garde la version précédente plutôt que d'afficher un feu faux, et une alerte est envoyée. Contrôles du ${fmtDate(C.date)} : ${nko?'<b class="warnc">'+nko+' en échec</b>':'tous réussis'}.</p>
 <table><tr><th>Témoin</th><th>Attendu</th><th>Observé</th><th></th></tr>${wit}</table>
 <h3 style="margin-top:16px">Fraîcheur de chaque donnée</h3><p class="note">Date de la dernière valeur utilisée, son âge et le rythme auquel la source publie. Une donnée plus ancienne que son rythme normal est signalée.</p>
 <table><tr><th>Source</th><th>Dernière valeur</th><th>Âge</th><th>Rythme de publication</th></tr>${(C['fraîcheur']||[]).map(f=>`<tr><td>${f.source}</td><td>${f.date?fmtDate(f.date):'—'}</td><td>${f['âge']==null?'—':f['âge']+' j'}</td><td>${f.rythme}</td></tr>`).join('')}</table>
 <details><summary>Contrôles de fraîcheur et de complétude</summary><table><tr><th>Contrôle</th><th>Observé</th><th></th></tr>${pub}</table></details>`;})();

// ---- Mon portefeuille ----
const KINDS=['ndx','sp500','world','btc','stock','other_equity','safe'];
function normPF(p){p=(p&&typeof p==='object')?p:{};p.targets=Object.assign({equity:60,stock:15,btc:10,safe:15,monthly:1000},(p.targets&&typeof p.targets==='object')?p.targets:{});
 p.lines=(Array.isArray(p.lines)?p.lines:[]).filter(l=>l&&+l.amount>0).map(l=>({label:String(l.label||''),kind:KINDS.includes(l.kind)?l.kind:'other_equity',ticker:String(l.ticker||''),amount:+l.amount,lev:[1,2,3].includes(+l.lev)?+l.lev:1,acct:String(l.acct||'Autre')}));return p;}
let PF=normPF(store('feux-portfolio'));
const stateOf=k=>D.states[k]||null;const stockOf=t=>S.find(s=>s.ticker&&t&&s.ticker.toUpperCase()===t.toUpperCase());
function lineColor(l){if(l.kind==='stock'){const s=stockOf(l.ticker);return s?s.color_confirmed:null;}if(l.kind==='other_equity')return (stateOf('world')||{}).color||null;if(l.kind==='safe')return null;return (stateOf(l.kind)||{}).color||null;}
function bucket(l){return l.kind==='safe'?'safe':l.kind==='btc'?'btc':l.kind==='stock'?'stock':'equity';}
function attention(l){const a=[];
 if(l.kind==='stock'){const s=stockOf(l.ticker);if(!s)return ['hors Top 100 : pas de lecture'];
  if(s.kind!=='operating')a.push('prix seul (pas de comptes SEC)');
  else{if(s.stale_accounts)a.push('comptes de plus de 15 mois');
   if((s.quality_fails||[]).length)a.push('solidité en échec ('+s.quality_fails.join(', ')+')');
   if(s.V!=null&&s.V>=80&&s.V_cross!=null&&s.V_cross>=80)a.push('chère contre son passé et contre les autres');}
  if(s.gsy)a.push('bulle GSY');else if(s.tendu)a.push('tendue');if(s.trend_broken)a.push('tendance cassée');}
 else if(l.kind!=='safe'&&l.kind!=='other_equity'){const st=stateOf(l.kind);if(st){if(st.cher)a.push(`cher (V ${Math.round(st.V)}) : montants exceptionnels en trois tranches`);if(st.falling_knife)a.push('couteau qui tombe');if(st.trend_broken)a.push('tendance cassée');}}
 if(l.lev>1)a.push(`levier ×${l.lev}`);return a;}
function savePF(){store('feux-portfolio',PF);}
$('#pf-add').onclick=()=>{const amt=parseFloat($('#pf-amount').value);if(!(amt>0))return msg('#pf-msg','Indiquez un montant.');msg('#pf-msg','');PF.lines.push({label:$('#pf-label').value||$('#pf-kind').selectedOptions[0].text,kind:$('#pf-kind').value,ticker:$('#pf-ticker').value.trim(),amount:amt,lev:parseInt($('#pf-lev').value),acct:$('#pf-acct').value});savePF();renderPF();$('#pf-amount').value='';$('#pf-label').value='';$('#pf-ticker').value='';};
$('#pf-save').onclick=()=>{PF.targets={equity:+$('#t-equity').value,stock:+$('#t-stock').value,btc:+$('#t-btc').value,safe:+$('#t-safe').value,monthly:+$('#t-monthly').value};savePF();renderPF();};
$('#pf-export').onclick=async()=>{const txt=JSON.stringify(PF,null,1);$('#pf-export-box').style.display='block';$('#pf-export-box textarea').value=txt;try{await navigator.clipboard.writeText(txt);msg('#pf-msg','Copié dans le presse-papiers (et affiché ci-dessous).');}catch(e){msg('#pf-msg','Copiez le texte ci-dessous pour le sauvegarder.');}};
$('#pf-import').onchange=e=>{const f=e.target.files[0];if(!f)return;const r=new FileReader();r.onload=()=>{try{PF=normPF(JSON.parse(r.result));savePF();renderPF();msg('#pf-msg','Portefeuille importé.');}catch(err){msg('#pf-msg','Fichier invalide.');}};r.readAsText(f);};
function renderPF(){const t=PF.targets;['equity','stock','btc','safe','monthly'].forEach(k=>{const e=$('#t-'+k);if(e)e.value=t[k];});
 const L=PF.lines;const total=L.reduce((a,l)=>a+l.amount,0);
 $('#pf-table').innerHTML='<tr><th>Ligne</th><th>Sous-jacent</th><th>Enveloppe</th><th>Montant</th><th>Levier</th><th>Exposition réelle</th><th>Feu du sous-jacent</th><th>Points d\'attention</th><th></th></tr>'+L.map((l,i)=>{const c=lineColor(l);const at=attention(l);return `<tr class="row${c||''}"><td>${esc(l.label)}</td><td>${$('#pf-kind option[value="'+l.kind+'"]').textContent}${l.ticker?' · '+esc(l.ticker):''}</td><td>${esc(l.acct)}</td><td>${eur(l.amount)}</td><td>×${l.lev}</td><td>${eur(l.amount*l.lev)}</td><td>${c?`<span class="c ${c}" style="font-weight:700">${LABEL[c]}</span>`:'—'}</td><td style="white-space:normal;min-width:180px">${at.length?at.map(x=>`<small class="pill${/échec|chère|bulle|couteau/.test(x)?' warnp':''}">${x}</small>`).join(' '):'<small class="note">rien à signaler</small>'}</td><td><button class="btn ghost" data-i="${i}">retirer</button></td></tr>`;}).join('')+(L.length?`<tr><th colspan="3">Total</th><th>${eur(total)}</th><th></th><th>${eur(L.reduce((a,l)=>a+l.amount*l.lev,0))}</th><th></th><th></th><th></th></tr>`:'');
 $$('#pf-table button').forEach(b=>b.onclick=()=>{PF.lines.splice(+b.dataset.i,1);savePF();renderPF();});
 if(!L.length){$('#pf-analysis').innerHTML='<p class="note">Ajoutez vos lignes pour obtenir l\'analyse.</p>';return;}
 const byB={equity:0,stock:0,btc:0,safe:0};L.forEach(l=>byB[bucket(l)]+=l.amount);const expo={equity:0,stock:0,btc:0,safe:0};L.forEach(l=>expo[bucket(l)]+=l.amount*l.lev);
 const red=L.filter(l=>lineColor(l)==='red').reduce((a,l)=>a+l.amount*l.lev,0);const green=L.filter(l=>lineColor(l)==='green').reduce((a,l)=>a+l.amount*l.lev,0);
 const eqExpo=expo.equity+expo.stock;const eqAmt=byB.equity+byB.stock;const levAmt=L.filter(l=>(bucket(l)==='equity'||bucket(l)==='stock')&&l.lev>1).reduce((a,l)=>a+l.amount,0);const levShare=eqAmt?levAmt/eqAmt:0;
 const btcLev=L.filter(l=>bucket(l)==='btc'&&l.lev>1);const bst=stateOf('btc')||{};
 const worst=['red','orange','green'].find(c=>Object.keys(D.states).filter(k=>k!=='btc').some(k=>D.states[k].color===c))||'orange';const broken=Object.keys(D.states).filter(k=>k!=='btc').some(k=>D.states[k].trend_broken);
 const cap=broken?D.conduct.lev_cap_broken:D.conduct.lev_cap[worst];const band=D.conduct.bands[worst];
 const pea=L.filter(l=>l.acct==='PEA').reduce((a,l)=>a+l.amount,0),cto=L.filter(l=>l.acct==='CTO').reduce((a,l)=>a+l.amount,0);
 const tech=L.filter(l=>l.kind==='ndx'||(l.kind==='stock'&&(stockOf(l.ticker)||{}).sector&&/Information Technology|Communication/.test(stockOf(l.ticker).sector))).reduce((a,l)=>a+l.amount*l.lev,0);
 const shock=(sE,sB)=>L.reduce((a,l)=>{const b=bucket(l);if(b==='safe')return a;const s=b==='btc'?sB:sE;return a+Math.min(l.amount,l.amount*l.lev*s);},0);
 const kp=(v,lab)=>`<div class="kpi"><b>${v}</b><span>${lab}</span></div>`;
 let html=`<div class="kpis">${kp(eur(total),'patrimoine saisi')}${kp(eur(eqExpo+expo.btc),'exposition réelle au risque (levier compté)')}${kp(pct(total?red/total:0),'part exposée à un feu ROUGE')}${kp(pct(levShare),`part de la poche actions en ETF à levier (plafond actuel ${pct(cap)})`)}${kp(pct(total?tech/total:0),'exposition tech / Nasdaq (levier compté)')}${kp(pct(total?pea/total:0)+' / '+pct(total?cto/total:0),'PEA / CTO')}</div>`;
 html+=`<h3>Test de résistance (perte en euros, levier compté, perte plafonnée au montant investi)</h3><table><tr><th>Scénario</th><th>Actions −20 % · Bitcoin −40 %</th><th>Actions −40 % · Bitcoin −60 %</th><th>Actions −60 % · Bitcoin −80 %</th></tr><tr><td>Perte</td><td>−${eur(shock(.2,.4))}</td><td>−${eur(shock(.4,.6))}</td><td>−${eur(shock(.6,.8))}</td></tr><tr><td>Patrimoine restant</td><td>${eur(total-shock(.2,.4))}</td><td>${eur(total-shock(.4,.6))}</td><td>${eur(total-shock(.6,.8))}</td></tr></table>`;
 const risky=L.filter(l=>bucket(l)!=='safe').reduce((a,l)=>a+l.amount*l.lev,0);const byT={};
 L.filter(l=>l.kind==='stock'&&l.ticker).forEach(l=>{const k=l.ticker.toUpperCase();byT[k]=(byT[k]||0)+l.amount*l.lev;});
 const conc=Object.entries(byT).filter(([k,v])=>risky&&v/risky>D.conduct.concentration_max);
 if(conc.length)html+=`<div class="warn">Concentration : ${conc.map(([k,v])=>`<b>${esc(k)}</b> pèse ${pct(v/risky)} de la poche risquée`).join(', ')} (seuil ${pct(D.conduct.concentration_max)}). Une société seule peut perdre 50 à 80 % sans que le marché baisse : ramener vers le seuil par les versements, ou préparer un arbitrage dans le Journal.</div>`;
 const flagged=L.filter(l=>l.kind==='stock'&&attention(l).some(x=>/échec|chère|bulle|comptes/.test(x)));
 if(flagged.length)html+=`<div class="detail"><b>Test d'échange</b> (${flagged.map(l=>esc(l.ticker||l.label)).join(', ')}) : la question n'est pas « faut-il vendre ? » mais « si cette somme était en liquide aujourd'hui, l'investirais-je dans cette ligne, à ce prix, plutôt que dans l'ETF monde ? ». Un « non » à deux revues de suite justifie de préparer un arbitrage dans le Journal (délai de ${D.conduct.hours} h, ${D.conduct.sell_cooling_days} jours en période de stress). Dans un PEA, l'arbitrage ne déclenche pas d'impôt ; dans un compte-titres, la plus-value est imposée.</div>`;
 if(btcLev.length&&(bst.color==='red'||bst.trend_broken))html+=`<div class="warn">Bitcoin à levier (${btcLev.map(l=>esc(l.label)).join(', ')}) alors que le feu Bitcoin est ${bst.color==='red'?'rouge':'en tendance cassée'} : les règles excluent tout produit à levier sur le Bitcoin dans cette situation.</div>`;
 if(levShare>cap+1e-9)html+=`<div class="warn">Levier au-dessus du plafond de la couleur du jour (${pct(levShare)} > ${pct(cap)}) : ramener l'excédent vers l'ETF sans levier (dans le PEA, sans impôt).</div>`;
 const tg={equity:t.equity,stock:t.stock,btc:t.btc,safe:t.safe};const names={equity:'Actions indices & monde',stock:'Actions individuelles',btc:'Bitcoin & proxys',safe:'Sans risque'};
 html+=`<h3>Écart à vos cibles (bandes ±${band} points au feu ${FR[worst]})</h3><table><tr><th>Poche</th><th>Poids actuel</th><th>Cible</th><th>Écart</th><th>Feu</th><th></th></tr>`;
 const colorB={equity:worst,stock:null,btc:(stateOf('btc')||{}).color,safe:null};
 Object.keys(tg).forEach(b=>{const w=total?100*byB[b]/total:0;const gap=w-tg[b];const c=colorB[b];html+=`<tr><td>${names[b]}</td><td>${w.toFixed(0)} %</td><td>${tg[b]} %</td><td>${gap>=0?'+':''}${gap.toFixed(0)} pt${Math.abs(gap)>band?' <b style="color:#b3261e">hors bande</b>':''}</td><td>${c?`<span class="c ${c}" style="font-weight:700">${LABEL[c]}</span>`:'—'}</td><td><div class="bar"><i style="width:${Math.min(100,w)}%;background:${c==='red'?'#b3261e':c==='green'?'#1a7f37':'#c7641a'}"></i></div></td></tr>`;});
 html+='</table>';
 // prochain versement : poches sous la cible. Bitcoin rouge : le versement va d'abord aux autres poches sous-pondérées.
 // Indices en rouge extrême (v1.1) : versement maintenu vers les mêmes supports (seuls les montants exceptionnels sont étalés).
 const under=Object.keys(tg).map(b=>({b,gap:tg[b]-(total?100*byB[b]/total:0),c:colorB[b]})).filter(x=>x.gap>0);
 const elig=under.filter(x=>!(x.b==='btc'&&x.c==='red'));const pool=elig.length?elig:under;const sum=pool.reduce((a,x)=>a+x.gap,0);
 html+=`<h3>Où va le versement de ${eur(t.monthly)} ce mois-ci</h3><ul class="plain" style="padding-left:18px">`+(pool.length?pool.map(x=>`<li>${names[x.b]} : <b>${eur(t.monthly*x.gap/sum)}</b> (sous la cible de ${x.gap.toFixed(0)} pt${x.c==='red'?(x.b==='btc'?' — feu rouge : versement régulier seulement, aucun montant exceptionnel':' — rouge extrême : versement maintenu, montants exceptionnels en six tranches mensuelles'):''})</li>`).join(''):'<li>Toutes les poches sont à la cible : répartir selon les cibles.</li>')+'</ul>';
 if(elig.length&&under.length>elig.length)html+=`<p class="note">Les poches en feu rouge sous leur cible (${under.filter(x=>x.b==='btc'&&x.c==='red').map(x=>names[x.b]).join(', ')}) ne reçoivent pas le versement ce mois-ci tant qu'une autre poche est sous sa cible : on rééquilibre par les flux, sans vendre.</p>`;
 $('#pf-analysis').innerHTML=html;}
try{renderPF();}catch(e){$('#pf-analysis').innerHTML='<div class="warn">Portefeuille illisible dans ce navigateur : importez une sauvegarde ou retirez les lignes.</div>';}

// ---- Journal ----
let J=store('feux-journal');J=Array.isArray(J)?J.filter(x=>x&&x.id):[];const Q=D.questions;
$('#j-questions').innerHTML=Q.map((q,i)=>`<label style="display:block;margin:4px 0;font-size:13px;color:var(--muted)">${q}<input data-q="${i}" style="width:100%;padding:6px 8px;border:1px solid var(--line);border-radius:6px"></label>`).join('');
function rates(){const a=$('#j-asset').value;const st=D.states[a];if(!st){$('#j-rates').textContent='Pour une action : voir sa fiche dans l\'onglet Actions.';return;}const br=(D.base_rates[a]||{})[st.color];
 $('#j-rates').innerHTML=`Feu <b>${LABEL[st.color]}</b> sur ${st.name}${st.trend_broken?' · tendance cassée':''}. `+(br?`Historiquement, après un jour ${FR[st.color]} : rendement médian <b>${pct(br.r1,1,true)}</b> à un an (négatif dans ${pct(br.neg1)} des cas), <b>${pct(br.r3,1,true)}/an</b> sur trois ans ; baisse médiane dans les 24 mois suivants <b>${pct(br.dd24)}</b> (plus de 20 % dans ${pct(br.dd20)} des cas).`:'');}
$('#j-asset').addEventListener('change',rates);rates();
const SELLQ=["Qu'est-ce qui a changé dans les faits, et pas seulement dans le prix ?","Le critère d'invalidation écrit à l'achat est-il atteint ?","Que deviendra l'argent, et pourquoi est-ce mieux ?"];
const REVQ=["La thèse s'est-elle vérifiée, dans les faits ?","Le critère d'invalidation a-t-il été atteint ?","Referais-je la même décision ? Qu'est-ce que j'en retiens ?"];
const qInput=(q,attr,i)=>`<label style="display:block;margin:4px 0;font-size:13px;color:var(--muted)">${q}<input ${attr}="${i}" style="width:100%;padding:6px 8px;border:1px solid var(--line);border-radius:6px"></label>`;
$('#j-sell').innerHTML='<b>Vente ou arbitrage : trois questions de plus</b>'+SELLQ.map((q,i)=>qInput(q,'data-sq',i)).join('');
function sellMode(){const v=$('#j-action').value;$('#j-sell').style.display=(v==='vendre'||v==='arbitrer')?'block':'none';}
$('#j-action').addEventListener('change',sellMode);sellMode();
function assetNow(a,tk){if(a==='stock'){const s=stockOf(tk);return s?{name:s.name,color:s.color_confirmed,price:s.price,drawdown:s.drawdown,trend_broken:s.trend_broken,falling_knife:false}:null;}return D.states[a]||null;}
function inStress(st,isStock){return !!st&&((!isStock&&st.color==='green')||st.falling_knife||(st.drawdown!=null&&st.drawdown>=D.conduct.stress_drawdown));}
function marketStress(){return Object.keys(D.states).filter(k=>k!=='btc').some(k=>inStress(D.states[k],false));}
const revDue=(it,now)=>it.status==='confirmé'&&!it.review&&it.confirmed&&(now-new Date(it.confirmed))/864e5>=D.conduct.review_days;
function renderJ(){const now=Date.now();$('#j-list').innerHTML=J.length?'<h3>Intentions</h3>'+J.slice().reverse().map(it=>{const el=(now-new Date(it.created))/36e5;const delay=it.delay_h||D.conduct.hours;const ok=el>=delay;
 const cur=assetNow(it.asset,it.ticker),p0=(it.snapshot||{}).price;const perfNow=(cur&&cur.price&&p0)?cur.price/p0-1:null;
 const rev=revDue(it,now)?`<div class="confirm-box" style="margin-top:8px"><b>Revue à ${D.conduct.review_days} jours</b> — ${perfNow==null?'':`depuis l'intention : <b>${pct(perfNow,1,true)}</b> (${it.action==='vendre'?'ce que la vente a évité, ou manqué':'ce que la décision a donné jusqu\'ici'}) · `}feu à l'intention ${LABEL[(it.snapshot||{}).color]||'—'}, aujourd'hui ${cur?LABEL[cur.color]||'—':'—'}.${REVQ.map((q,i)=>qInput(q,'data-rq',i)).join('')}<button class="btn" data-id="${it.id}" data-a="review">Enregistrer la revue</button> <span class="note" data-rmsg="${it.id}"></span></div>`:'';
 const done=it.review?`<br><i>Revue du ${fmtDate(it.review.date)}</i>${it.review.perf==null?'':' ('+pct(it.review.perf,1,true)+' depuis l\'intention)'} : ${it.review.answers.map(esc).join(' / ')}`:'';
 return `<div class="detail"><b>${new Date(it.created).toLocaleString('fr-FR')}</b> — ${esc(it.action)} ${esc(it.assetName)}${it.ticker?' ('+esc(it.ticker)+')':''} ${eur(it.amount)} · état : <b>${esc(it.status)}</b>${it.snapshot?` · feu à l'intention : ${LABEL[it.snapshot.color]||'—'}`:''}<br><i>Thèse :</i> ${esc(it.thesis)||'—'} · <i>Invalidation :</i> ${esc(it.inval)||'—'}<br>${it.rates?`<span class="note">${esc(it.rates)}</span><br>`:''}
 ${it.sell?`<i>Vente :</i> ${it.sell.map(esc).join(' / ')}${it.stress?` <b class="warnc">(période de stress : délai ${Math.round(delay/24)} jours)</b>`:''}<br>`:''}${done}${rev}
 ${it.status==='en attente'?`<button class="btn" data-id="${it.id}" data-a="confirm" ${ok?'':'disabled'}>${ok?'Confirmer (les cinq questions sont redemandées)':'Confirmation possible dans '+(delay-el>48?Math.ceil((delay-el)/24)+' jours':Math.ceil(delay-el)+' h')}</button> <button class="btn ghost" data-id="${it.id}" data-a="cancel">Annuler</button><div class="confirm-box" data-for="${it.id}" style="display:none;margin-top:8px">${Q.map((q,i)=>`<label style="display:block;margin:4px 0;font-size:13px;color:var(--muted)">${q}<input data-cq="${i}" style="width:100%;padding:6px 8px;border:1px solid var(--line);border-radius:6px"></label>`).join('')}<button class="btn" data-id="${it.id}" data-a="confirm2">Valider la confirmation</button> <span class="note" data-cmsg="${it.id}"></span></div>`:''}</div>`;}).join('')+'<button class="btn ghost" id="j-export">Copier le journal (JSON)</button><div id="j-export-box" style="display:none"><textarea style="width:100%;height:120px;font-size:12px"></textarea></div><p class="note" id="j-msg"></p>':'<p class="note">Aucune intention enregistrée.</p>';
 $$('#j-list button[data-a]').forEach(b=>b.onclick=()=>{const it=J.find(x=>x.id===b.dataset.id);const a=b.dataset.a;
  if(a==='cancel'){it.status='annulé';store('feux-journal',J);renderJ();return;}
  if(a==='review'){const box=b.closest('.confirm-box');const ans=Array.from(box.querySelectorAll('input[data-rq]')).map(i=>i.value.trim());if(ans.some(x=>!x)){box.querySelector('[data-rmsg]').textContent='Les trois réponses sont obligatoires.';return;}
   const cur=assetNow(it.asset,it.ticker),p0=(it.snapshot||{}).price;it.review={date:new Date().toISOString(),answers:ans,perf:(cur&&cur.price&&p0)?cur.price/p0-1:null,color_now:cur?cur.color:null};store('feux-journal',J);renderJ();return;}
  if(a==='confirm'){const box=$(`.confirm-box[data-for="${it.id}"]`);box.style.display=box.style.display==='none'?'block':'none';return;}
  if(a==='confirm2'){const box=$(`.confirm-box[data-for="${it.id}"]`);const ans=Array.from(box.querySelectorAll('input[data-cq]')).map(i=>i.value.trim());if(ans.some(x=>!x)){box.querySelector('[data-cmsg]').textContent='Les cinq réponses sont obligatoires.';return;}it.status='confirmé';it.confirmed=new Date().toISOString();it.answers2=ans;store('feux-journal',J);renderJ();}});
 const due=J.filter(it=>revDue(it,now)).length;const jb=$('nav.tabs button[data-t="journal"]');if(jb)jb.textContent='Journal'+(due?` (${due} revue${due>1?'s':''} à faire)`:'');
 const ex=$('#j-export');if(ex)ex.onclick=async()=>{const txt=JSON.stringify(J,null,1);$('#j-export-box').style.display='block';$('#j-export-box textarea').value=txt;try{await navigator.clipboard.writeText(txt);msg('#j-msg','Copié dans le presse-papiers (et affiché ci-dessous).');}catch(e){msg('#j-msg','Copiez le texte ci-dessous pour le sauvegarder.');}};}
$('#j-add').onclick=()=>{const ans=$$('#j-questions input').map(i=>i.value.trim());if(ans.some(a=>!a))return msg('#j-add-msg','Répondez aux cinq questions avant d\'enregistrer.');
 const a=$('#j-asset').value,tk=$('#j-ticker').value.trim(),act=$('#j-action').value;const st=assetNow(a,tk);const sell=act==='vendre'||act==='arbitrer';let sellAns=null;
 if(sell){sellAns=$$('#j-sell input').map(i=>i.value.trim());if(sellAns.some(x=>!x))return msg('#j-add-msg','Vente ou arbitrage : répondez aussi aux trois questions de vente.');}
 const stress=sell&&(inStress(st,a==='stock')||(a==='stock'&&marketStress()));msg('#j-add-msg',stress?`Vente en période de stress : confirmation possible dans ${D.conduct.sell_cooling_days} jours, le temps de relire ce que l'histoire dit de cette situation.`:'');
 J.push({id:Math.random().toString(36).slice(2,10),created:new Date().toISOString(),asset:a,assetName:st?st.name:'Action',ticker:tk,action:act,amount:+$('#j-amount').value||0,thesis:$('#j-thesis').value,inval:$('#j-inval').value,answers:ans,sell:sellAns,stress,delay_h:stress?24*D.conduct.sell_cooling_days:D.conduct.hours,
  snapshot:st?{color:st.color,trend_broken:st.trend_broken,price:st.price,drawdown:st.drawdown}:null,rates:$('#j-rates').textContent,status:'en attente'});
 store('feux-journal',J);$$('#j-questions input').forEach(i=>i.value='');$$('#j-sell input').forEach(i=>i.value='');$('#j-thesis').value='';$('#j-inval').value='';$('#j-amount').value='';renderJ();};
renderJ();
})();
"""
