"""Contrôles avant publication (bloquants) et témoins (attendu / observé), repris de Kairys Lite et Kairys Alpha.

- Contrôles de publication : si les données du jour sont incomplètes ou trop anciennes, le workflow s'arrête avant de publier,
  et le site garde la version précédente (publication « fail-closed »).
- Témoins : des comportements que le code DOIT avoir, vérifiés sur les sorties du jour et affichés dans l'onglet Validation.
  Un témoin « critique » en échec bloque aussi la publication.
"""
from __future__ import annotations

import datetime as dt
import json
import logging

import pandas as pd

from .config import DOCS_DIR, rules

log = logging.getLogger("feux.check")
MAX_AGE_DAYS = {"sp500": 5, "ndx": 5, "world": 5, "btc": 4}


def _load(name: str) -> dict:
    p = DOCS_DIR / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def publication_checks() -> list[dict]:
    out = []
    lat = _load("latest.json")
    today = dt.date.today()
    for k, max_age in MAX_AGE_DAYS.items():
        d = lat.get(k, {})
        date = d.get("date")
        age = (today - dt.date.fromisoformat(date)).days if date else None
        out.append({"contrôle": f"{k} : données de moins de {max_age} jours", "observé": f"{date} ({age} j)" if date else "absent",
                    "ok": age is not None and age <= max_age, "bloquant": True})
        out.append({"contrôle": f"{k} : couleur calculée", "observé": d.get("color_confirmed"),
                    "ok": d.get("color_confirmed") in ("green", "orange", "red", "none"), "bloquant": True})
    # entrées des indices : un flux mort ne doit pas être utilisé en silence (v1.0.1)
    from . import store
    for name, label, max_age, blocking in (("vix", "VIX (FRED)", 7, True), ("credit_spread", "écart de crédit Baa (FRED)", 7, True),
                                           ("shiller_P", "dernier mois de Shiller", 75, True)):
        try:
            last = pd.Timestamp(store.load(name)["ref_date"].max()).date()
            age = (today - last).days
            out.append({"contrôle": f"{label} : moins de {max_age} jours", "observé": f"{last} ({age} j)", "ok": age <= max_age, "bloquant": blocking})
        except Exception as exc:   # série absente
            out.append({"contrôle": f"{label} : présent", "observé": str(exc)[:80], "ok": False, "bloquant": blocking})
    # couverture des actions : non bloquante (une panne de la SEC ne doit pas empêcher la mise à jour des feux des indices et
    # du Bitcoin ; les sociétés sans comptes passent en « prix seul », ce qui est affiché) — les témoins, eux, restent bloquants
    st = _load("stocks_latest.json")
    n_val = sum(1 for s in st.values() if s.get("V") is not None)
    out.append({"contrôle": "actions : au moins 80 sociétés suivies", "observé": len(st), "ok": len(st) >= 80, "bloquant": False})
    out.append({"contrôle": "actions : au moins 60 valorisées (comptes SEC)", "observé": n_val, "ok": n_val >= 60, "bloquant": False})
    old_px = [s.get("ticker") for s in st.values() if s.get("date") and (today - dt.date.fromisoformat(s["date"])).days > 7]
    out.append({"contrôle": "actions : cours de moins de 7 jours", "observé": ", ".join(old_px) or f"{len(st)} à jour",
                "ok": not old_px, "bloquant": False})
    return out


def witnesses() -> list[dict]:
    lat, st = _load("latest.json"), _load("stocks_latest.json")
    r = rules()
    by_t = {(s.get("ticker") or k): s for k, s in st.items()}
    w = []

    def add(desc, expected, observed, ok, critical=False):
        w.append({"témoin": desc, "attendu": expected, "observé": observed, "ok": bool(ok), "critique": critical})

    idx = [lat.get(k, {}) for k in ("sp500", "ndx", "world")]
    red_min = r["indices"]["valuation"].get("red_min", 101)

    def _idx_ok(d):
        V, c = d.get("V"), d.get("color")
        if V is None:
            return c in ("none", "green")          # sans valorisation : pas de feu (sauf capitulation)
        if V >= red_min:
            return c == "red"
        return c in ("green", "orange")
    add(f"Indices : rouge si et seulement si V ≥ {red_min:g} (rouge extrême, v1.1)", f"rouge ⇔ V ≥ {red_min:g}",
        ", ".join(f"{d.get('color')} (V {d['V']:.1f})" if d.get("V") is not None else str(d.get("color")) for d in idx),
        all(_idx_ok(d) for d in idx), critical=True)
    sp = lat.get("sp500", {})
    if sp.get("cape_live") and sp.get("V") is not None:
        add("S&P 500 : un CAPE au-dessus de 30 est « cher » (V ≥ 80) contre l'histoire depuis 1881", "cher si CAPE > 30",
            f"CAPE {sp['cape_live']:.1f}, V {sp['V']:.0f}, cher {sp.get('cher')}", sp["cape_live"] <= 30 or bool(sp.get("cher")), critical=True)
    if sp.get("er10") is not None:
        add("Rendement réel attendu à 10 ans dans une plage plausible", "entre −10 % et +15 %/an", f"{100 * sp['er10']:+.1f} %/an",
            -0.10 <= sp["er10"] <= 0.15)
    b = lat.get("btc", {})
    if b:
        have = b.get("mvrv") is not None and b.get("ratio_200w") is not None
        if have:
            expect = ("green" if (b["mvrv"] < r["bitcoin"]["green"]["mvrv_max"] or b["ratio_200w"] < 1)
                      else "red" if b["mvrv"] >= r["bitcoin"]["red"]["mvrv_min"] else "orange")
            obs = f"{b.get('color')} (MVRV {b['mvrv']:.2f}, prix/MM200s {b['ratio_200w']:.2f})"
        else:
            expect, obs = "none", f"{b.get('color')} (MVRV ou moyenne 200 semaines manquant)"
        add("Bitcoin : la couleur brute suit la règle B1 (niveaux) ; sans MVRV ou sans moyenne 200 semaines, pas de feu", expect, obs,
            b.get("color") == expect, critical=True)
    # (v1.0.1) un témoin dont la liste est vide échoue : il ne doit pas réussir faute de cas à vérifier
    banks = [t for t in ("JPM", "BAC", "WFC", "HSBA.L", "RY.TO", "8306.T") if t in by_t and by_t[t].get("kind") == "operating"]
    add("Banques en mode P/E et P/B (EV et flux libre n'ont pas de sens)", "financial (au moins 3 banques)", ", ".join(f"{t}:{by_t[t].get('mode')}" for t in banks) or "aucune",
        len(banks) >= 3 and all(by_t[t].get("mode") == "financial" for t in banks))
    pay = [t for t in ("V", "MA") if t in by_t and by_t[t].get("kind") == "operating"]
    add("Réseaux de paiement en mode industriel", "industrial (Visa et Mastercard)", ", ".join(f"{t}:{by_t[t].get('mode')}" for t in pay) or "aucun",
        len(pay) == 2 and all(by_t[t].get("mode") == "industrial" for t in pay))
    reits = [s for s in st.values() if s.get("mode") == "reit"]
    add("Une foncière n'est jamais verte", "aucune foncière verte (au moins une foncière suivie)",
        f"{len(reits)} foncière(s), vertes : {sum(1 for s in reits if s.get('color_confirmed') == 'green')}",
        len(reits) >= 1 and all(s.get("color_confirmed") != "green" for s in reits))
    stale = [s for s in st.values() if s.get("stale_accounts") and s.get("kind") == "operating"]
    add("Comptes de plus de 15 mois : pas de feu (jamais un orange par défaut)", "pas de feu", ", ".join(f"{s.get('ticker')}:{s.get('color_confirmed')}" for s in stale) or "aucune",
        all(s.get("color_confirmed") == "none" for s in stale), critical=True)
    ind = [s for s in st.values() if s.get("kind") == "operating" and s.get("mode") == "industrial" and not s.get("stale_accounts")]
    no_debt = [s.get("ticker") for s in ind if s.get("debt") is None]
    add("Dette connue (sociétés industrielles aux comptes récents) ; inconnue = pas d'EV ni de test de dette, jamais zéro",
        "au plus 3 inconnues", ", ".join(no_debt) or f"connue pour les {len(ind)}", len(no_debt) <= 3)
    ev_wo_debt = [s.get("ticker") for s in ind if s.get("debt") is None and s.get("ev") is not None]
    add("Aucune valeur d'entreprise calculée avec une dette inconnue", "aucune", ", ".join(ev_wo_debt) or "aucune", not ev_wo_debt, critical=True)
    no_fcf = [s.get("ticker") for s in ind if s.get("fcf") is None]
    add("Flux libre connu (sociétés industrielles aux comptes récents) ; capex ancien jamais reporté", "au plus 8 inconnus",
        ", ".join(no_fcf) or f"connu pour les {len(ind)}", len(no_fcf) <= 8)
    po = [s for s in st.values() if s.get("kind") == "price_only"]
    add("Sans comptes à la SEC : pas de feu", "pas de feu", f"{len(po)} sociétés, colorées : {sum(1 for s in po if s.get('color_confirmed') != 'none')}",
        bool(po) and all(s.get("color_confirmed") == "none" for s in po), critical=True)
    nl = [s for s in st.values() if s.get("color_confirmed") == "none" and s.get("kind") == "operating"]
    add("Action sans feu : raison écrite", "raison pour chacune", f"{len(nl)} sans feu, sans raison : "
        + (", ".join(s.get("ticker") for s in nl if not s.get("no_light_reason")) or "aucune"),
        all(s.get("no_light_reason") for s in nl), critical=True)
    th = _load("themes_latest.json")
    try:
        from .themes import overlay
        rows = overlay(st)
        bad = [r["name"] for r in rows if r["light"]["color_confirmed"] == "none" and not r["light"]["reason"]]
        col = [r["name"] for r in rows if r["light"]["color_confirmed"] != "none" and r["light"]["V"] is None]
        add("Zones, secteurs et thèmes : une valorisation seulement avec une mesure, sinon une raison écrite", "toujours",
            f"{len(rows)} lignes ; sans raison : {', '.join(bad) or 'aucune'} ; affichées sans mesure : {', '.join(col) or 'aucune'}",
            bool(rows) and not bad and not col, critical=True)
        if r["themes"].get("valuation", {}).get("status") == "information":
            lit = [x["name"] for x in rows if x["light"]["color_confirmed"] not in ("info", "none")]
            add("Zones, secteurs et thèmes : aucun feu de couleur (information seulement, test du 9 novembre 2026)", "aucun",
                ", ".join(lit) or "aucun", not lit, critical=True)
        old_z = [r["name"] for r in rows if r.get("date") and (dt.date.today() - dt.date.fromisoformat(r["date"])).days > 7]
        add("Zones, secteurs et thèmes : cours de moins de 7 jours", "tous", ", ".join(old_z) or f"{len(rows)} à jour", not old_z)
    except Exception as exc:
        add("Zones, secteurs et thèmes : calculables", "oui", str(exc)[:80], False, critical=True)
    neg = [s.get("ticker") for s in st.values() if s.get("fcf") is not None and s.get("fcf_gross") is not None and s["fcf"] > s["fcf_gross"] + 1]
    add("Flux libre net de la rémunération en actions ≤ flux libre brut", "toujours", "écarts : " + (", ".join(neg) or "aucun"), not neg, critical=True)
    try:
        from .prereg import verify_hashes
        vh = verify_hashes()
        add("Pré-inscriptions : empreintes recalculées identiques à celles inscrites", "toutes identiques",
            ", ".join(f"{v['date']}:{'ok' if v['ok'] else 'DIFFÉRENTE'}" for v in vh) or "aucune inscription", all(v["ok"] for v in vh), critical=True)
    except Exception as exc:
        add("Pré-inscriptions : empreintes recalculées", "vérifiables", str(exc)[:80], False, critical=True)
    no_mcap = [s.get("ticker") for s in st.values() if s.get("kind") == "operating" and s.get("mcap") is None]
    add("Capitalisation connue pour les sociétés aux comptes SEC", "au plus 3 inconnues", ", ".join(no_mcap) or "toutes connues", len(no_mcap) <= 3)
    jumps, n = share_count_jumps()
    add(f"Nombre d'actions implicite (capitalisation / cours) sans saut de plus de 50 % d'un jour à l'autre sur dix ans ({n} sociétés) : "
        "divisions d'actions, erreurs d'échelle et valeurs aberrantes de la SEC traitées", "aucun saut", ", ".join(jumps) or "aucun",
        not jumps, critical=True)
    return w


def share_count_jumps(years: int = 10, limit: float = 1.5) -> tuple[list[str], int]:
    """Un saut du nombre d'actions implicite trahit une division mal prise en compte ou une donnée SEC à la mauvaise échelle :
    la capitalisation historique, donc la position de la valorisation contre son passé, serait fausse."""
    from .config import ROOT

    out, n = [], 0
    for p in sorted((ROOT / "data" / "signals" / "stocks").glob("*.parquet")):
        df = pd.read_parquet(p)
        if "mcap" not in df or df["mcap"].dropna().empty:
            continue
        n += 1
        sh = (df["mcap"] / df["price_in_accounts_ccy"]).where(lambda x: x > 0).dropna()
        sh = sh[sh.index >= sh.index.max() - pd.DateOffset(years=years)]
        r = (sh / sh.shift(1)).dropna()
        bad = r[(r > limit) | (r < 1 / limit)]
        if len(bad):
            out.append(f"{p.stem} {bad.index[0].date()} ×{bad.iloc[0]:.2f}" + (f" (+{len(bad) - 1})" if len(bad) > 1 else ""))
    return out, n


def freshness() -> list[dict]:
    """Chaque source : date de sa dernière valeur, âge, et rythme de publication attendu (onglet Validation)."""
    from . import store

    today = dt.date.today()
    rows = []

    def add(src, name_or_date, cadence):
        try:
            d = (pd.Timestamp(store.load(name_or_date)["ref_date"].max()).date() if isinstance(name_or_date, str) and not name_or_date[:4].isdigit()
                 else dt.date.fromisoformat(str(name_or_date)[:10]))
        except Exception:
            d = None
        now = dt.datetime.now(dt.timezone.utc)
        if d == today and "séance" in cadence and now.hour < 21:       # cours en séance : pas encore une clôture
            d = today - dt.timedelta(days={0: 3, 6: 2}.get(today.weekday(), 1))
        rows.append({"source": src, "date": str(d) if d else None, "âge": (today - d).days if d else None, "rythme": cadence})

    add("S&P 500, Nasdaq-100 (Yahoo Finance)", "px_sp500", "chaque séance, clôture")
    add("MSCI World (Yahoo Finance)", "px_world", "chaque séance, clôture")
    add("VIX (FRED, complété par Yahoo pour les derniers jours)", "px_vix_yahoo", "chaque séance")
    add("Écart de crédit Baa − 10 ans (FRED)", "credit_spread", "chaque séance, publié le lendemain")
    add("CAPE de Shiller : dernier mois de prix", "shiller_P", "mensuel")
    add("CAPE de Shiller : derniers bénéfices", "shiller_E", "trimestriel, environ 3 mois de décalage")
    add("Dette sur marge (FINRA)", "margin_debt", "mensuel, environ 3 semaines de décalage")
    add("Allocation des ménages en actions (Fed Z.1)", "aiae", "trimestriel, environ 10 semaines de décalage")
    add("Bitcoin : prix (Coin Metrics, complété par Yahoo)", "px_btc_yahoo", "quotidien")
    add("Bitcoin : MVRV (Coin Metrics)", "btc_mvrv", "quotidien, 1 à 2 jours de décalage")
    st = _load("stocks_latest.json")
    if st:
        px_dates = [s.get("date") for s in st.values() if s.get("date")]
        rows.append({"source": "Actions du Top 100 : cours (Yahoo Finance)", "date": min(px_dates) if px_dates else None,
                     "âge": (today - dt.date.fromisoformat(min(px_dates))).days if px_dates else None, "rythme": "chaque séance (la plus ancienne)"})
        acc = sorted((s.get("accounts_as_of"), s.get("ticker")) for s in st.values() if s.get("accounts_as_of") and s.get("kind") == "operating")
        if acc:
            rows.append({"source": f"Actions : comptes SEC les plus anciens ({acc[0][1]})", "date": acc[0][0],
                         "âge": (today - dt.date.fromisoformat(acc[0][0])).days, "rythme": "trimestriel (10-Q) ou annuel (20-F, 40-F)"})
    th = _load("themes_latest.json")
    if th:
        dates = [v.get("date") for v in th.values() if v.get("date")]
        rows.append({"source": f"Zones, secteurs et thèmes : cours des {len(dates)} ETF (le plus ancien)", "date": min(dates),
                     "âge": (today - dt.date.fromisoformat(min(dates))).days, "rythme": "chaque séance"})
    return rows


def run() -> bool:
    pc, ws = publication_checks(), witnesses()
    (DOCS_DIR / "checks.json").write_text(json.dumps({"publication": pc, "témoins": ws, "fraîcheur": freshness(), "date": dt.date.today().isoformat()},
                                                     ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    bad = [c for c in pc if not c["ok"] and c["bloquant"]] + [w for w in ws if not w["ok"] and w["critique"]]
    for c in pc:
        (log.info if c["ok"] else log.error if c["bloquant"] else log.warning)("%s %s : %s", "OK " if c["ok"] else "KO ", c["contrôle"], c["observé"])
    for w in ws:
        (log.info if w["ok"] else (log.error if w["critique"] else log.warning))("%s %s : %s", "OK " if w["ok"] else "KO ", w["témoin"], w["observé"])
    if bad:
        log.error("%d contrôle(s) bloquant(s) en échec : publication annulée", len(bad))
    return not bad
