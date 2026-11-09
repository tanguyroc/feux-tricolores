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
                    "ok": d.get("color_confirmed") in ("green", "orange", "red"), "bloquant": True})
    # couverture des actions : non bloquante (une panne de la SEC ne doit pas empêcher la mise à jour des feux des indices et
    # du Bitcoin ; les sociétés sans comptes passent en « prix seul », ce qui est affiché) — les témoins, eux, restent bloquants
    st = _load("stocks_latest.json")
    n_val = sum(1 for s in st.values() if s.get("V") is not None)
    out.append({"contrôle": "actions : au moins 80 sociétés suivies", "observé": len(st), "ok": len(st) >= 80, "bloquant": False})
    out.append({"contrôle": "actions : au moins 60 valorisées (comptes SEC)", "observé": n_val, "ok": n_val >= 60, "bloquant": False})
    return out


def witnesses() -> list[dict]:
    lat, st = _load("latest.json"), _load("stocks_latest.json")
    r = rules()
    by_t = {(s.get("ticker") or k): s for k, s in st.items()}
    w = []

    def add(desc, expected, observed, ok, critical=False):
        w.append({"témoin": desc, "attendu": expected, "observé": observed, "ok": bool(ok), "critique": critical})

    idx = [lat.get(k, {}) for k in ("sp500", "ndx", "world")]
    add("Indices : plus de rouge depuis la v1.0 (protocole §8.4)", "vert ou orange", ", ".join(str(d.get("color")) for d in idx),
        all(d.get("color") in ("green", "orange") for d in idx), critical=True)
    sp = lat.get("sp500", {})
    if sp.get("cape_live") and sp.get("V") is not None:
        add("S&P 500 : un CAPE au-dessus de 30 est « cher » (V ≥ 80) contre l'histoire depuis 1881", "cher si CAPE > 30",
            f"CAPE {sp['cape_live']:.1f}, V {sp['V']:.0f}, cher {sp.get('cher')}", sp["cape_live"] <= 30 or bool(sp.get("cher")), critical=True)
    if sp.get("er10") is not None:
        add("Rendement réel attendu à 10 ans dans une plage plausible", "entre −10 % et +15 %/an", f"{100 * sp['er10']:+.1f} %/an",
            -0.10 <= sp["er10"] <= 0.15)
    b = lat.get("btc", {})
    if b.get("mvrv") is not None and b.get("ratio_200w") is not None:
        expect = "green" if (b["mvrv"] < r["bitcoin"]["green"]["mvrv_max"] or b["ratio_200w"] < 1) else ("red" if b["mvrv"] >= r["bitcoin"]["red"]["mvrv_min"] else "orange")
        add("Bitcoin : la couleur brute suit la règle B1 (niveaux)", expect, f"{b.get('color')} (MVRV {b['mvrv']:.2f}, prix/MM200s {b['ratio_200w']:.2f})",
            b.get("color") == expect, critical=True)
    banks = [t for t in ("JPM", "BAC", "WFC", "HSBA.L", "RY.TO", "8306.T") if t in by_t and by_t[t].get("kind") == "operating"]
    add("Banques en mode P/E et P/B (EV et flux libre n'ont pas de sens)", "financial", ", ".join(f"{t}:{by_t[t].get('mode')}" for t in banks),
        all(by_t[t].get("mode") == "financial" for t in banks))
    pay = [t for t in ("V", "MA") if t in by_t and by_t[t].get("kind") == "operating"]
    add("Réseaux de paiement en mode industriel", "industrial", ", ".join(f"{t}:{by_t[t].get('mode')}" for t in pay),
        all(by_t[t].get("mode") == "industrial" for t in pay))
    reits = [s for s in st.values() if s.get("mode") == "reit"]
    add("Une foncière n'est jamais verte", "aucune foncière verte", f"{len(reits)} foncière(s), vertes : {sum(1 for s in reits if s.get('color') == 'green')}",
        all(s.get("color") != "green" for s in reits))
    stale = [s for s in st.values() if s.get("stale_accounts") and s.get("kind") == "operating"]
    add("Comptes de plus de 15 mois : jamais colorée", "orange", ", ".join(f"{s.get('ticker')}:{s.get('color')}" for s in stale) or "aucune",
        all(s.get("color") == "orange" for s in stale), critical=True)
    po = [s for s in st.values() if s.get("kind") == "price_only"]
    add("Sans comptes à la SEC : prix seul, orange", "orange", f"{len(po)} sociétés, colorées : {sum(1 for s in po if s.get('color') != 'orange')}",
        all(s.get("color") == "orange" for s in po))
    neg = [s.get("ticker") for s in st.values() if s.get("fcf") is not None and s.get("fcf_gross") is not None and s["fcf"] > s["fcf_gross"] + 1]
    add("Flux libre net de la rémunération en actions ≤ flux libre brut", "toujours", "écarts : " + (", ".join(neg) or "aucun"), not neg, critical=True)
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


def run() -> bool:
    pc, ws = publication_checks(), witnesses()
    (DOCS_DIR / "checks.json").write_text(json.dumps({"publication": pc, "témoins": ws, "date": dt.date.today().isoformat()},
                                                     ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    bad = [c for c in pc if not c["ok"] and c["bloquant"]] + [w for w in ws if not w["ok"] and w["critique"]]
    for c in pc:
        (log.info if c["ok"] else log.error if c["bloquant"] else log.warning)("%s %s : %s", "OK " if c["ok"] else "KO ", c["contrôle"], c["observé"])
    for w in ws:
        (log.info if w["ok"] else (log.error if w["critique"] else log.warning))("%s %s : %s", "OK " if w["ok"] else "KO ", w["témoin"], w["observé"])
    if bad:
        log.error("%d contrôle(s) bloquant(s) en échec : publication annulée", len(bad))
    return not bad
