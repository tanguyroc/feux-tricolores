"""Hors-échantillon futur : archive quotidienne des états et pré-inscriptions datées et hachées.

- `history/states.csv` (ajout seul) : état de chaque indice et du Bitcoin chaque jour de calcul.
- `history/stocks_states.csv` (ajout seul) : état indicatif de chaque action.
- `prereg/AAAA-MM-JJ.json` : ce que les règles affirment ce jour-là (couleur, attentes historiques par couleur, hypothèses à
  tester) et les dates auxquelles ce sera jugé. L'empreinte SHA-256 du contenu est inscrite dans `prereg/HASHES.txt` ; le commit
  git horodaté fait foi. Rien de ce qui est inscrit n'est ensuite modifié.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging

import numpy as np
import pandas as pd

from .config import DOCS_DIR, ROOT, rules

log = logging.getLogger("feux.prereg")
HIST_DIR = ROOT / "history"
PREREG_DIR = ROOT / "prereg"
HORIZONS = {"1 an": 1, "3 ans": 3}
INDEX_KEYS = ("sp500", "ndx", "world")


def _clean(v):
    if v is None:
        return None
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else round(float(v), 6)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def _latest() -> dict:
    return json.loads((DOCS_DIR / "latest.json").read_text(encoding="utf-8"))


def _stocks_latest() -> dict:
    p = DOCS_DIR / "stocks_latest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


# ----------------------------------------------------------------------------------------------
# Archive quotidienne
# ----------------------------------------------------------------------------------------------
def _session_closed(data_date, now: dt.datetime | None = None) -> bool:
    """Une valeur datée d'aujourd'hui avant 21 h UTC (clôture de New York, été comme hiver) est intrajournalière :
    on ne l'archive pas (l'archive est en ajout seul : la première valeur inscrite pour une date resterait)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    return not (data_date and str(data_date) == now.date().isoformat() and now.hour < 21)


def archive_today() -> int:
    HIST_DIR.mkdir(exist_ok=True)
    version = str(rules()["version"])
    lat = _latest()
    rows = []
    for key, d in lat.items():
        if not _session_closed(d.get("date")):
            log.info("Archive : %s daté d'aujourd'hui avant la clôture, non archivé", key)
            continue
        rows.append({"date_calcul": dt.date.today().isoformat(), "date_données": d.get("date"), "actif": key, "règles": version,
                     "couleur": d.get("color"), "couleur_confirmée": d.get("color_confirmed"), "cher": d.get("cher"),
                     "cher_tendu": d.get("cher_tendu"), "tendance_cassée": d.get("trend_broken"), "V": _clean(d.get("V")),
                     "rdt_attendu_10a": _clean(d.get("er10")), "prix": _clean(d.get("price")), "mvrv": _clean(d.get("mvrv")),
                     "prix_mm200s": _clean(d.get("ratio_200w"))})
    n = _append(HIST_DIR / "states.csv", rows, key=("date_données", "actif"))
    srows = []
    for key, s in _stocks_latest().items():
        if not _session_closed(s.get("date")):
            continue
        srows.append({"date_calcul": dt.date.today().isoformat(), "date_données": s.get("date"), "ticker": s.get("ticker") or key,
                      "règles": version, "couleur": s.get("color"), "couleur_confirmée": s.get("color_confirmed"),
                      "V": _clean(s.get("V")), "V_cross": _clean(s.get("V_cross")), "solide": s.get("quality_ok"),
                      "prix": _clean(s.get("price")), "devise": s.get("price_currency")})
    n += _append(HIST_DIR / "stocks_states.csv", srows, key=("date_données", "ticker"))
    log.info("Archive : %d lignes ajoutées", n)
    return n


def _append(path, rows: list[dict], key: tuple) -> int:
    new = pd.DataFrame(rows)
    if new.empty:
        return 0
    if path.exists():
        old = pd.read_csv(path, dtype=str)
        have = set(map(tuple, old[list(key)].astype(str).to_numpy()))
        new = new[[tuple(map(str, r)) not in have for r in new[list(key)].to_numpy()]]
        if new.empty:
            return 0
        new.to_csv(path, mode="a", header=False, index=False)
    else:
        new.to_csv(path, index=False)
    return len(new)


# ----------------------------------------------------------------------------------------------
# Pré-inscription
# ----------------------------------------------------------------------------------------------
def _base_rates() -> dict:
    p = DOCS_DIR / "backtest_summary.json"
    if not p.exists():
        return {}
    s = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for a in list(INDEX_KEYS) + ["btc"]:
        if a not in s:
            continue
        out[a] = {}
        for r in s[a]["fwd"]:
            if r["horizon"] in HORIZONS:
                out[a].setdefault(r["couleur"], {})[r["horizon"]] = {"médiane": _clean(r["médiane_annualisée"]),
                                                                       "p10": _clean(r["p10_annualisé"]),
                                                                       "part_négative": _clean(r["part_négative"])}
    return out


def register(day: str | None = None) -> dict:
    """Écrit prereg/<jour>.json (une seule fois par jour) et son empreinte. Seulement à la date du jour : une inscription
    antidatée ou postdatée n'aurait aucune valeur probante (v1.0.1)."""
    PREREG_DIR.mkdir(exist_ok=True)
    today = dt.date.today().isoformat()
    if day and day != today:
        raise ValueError(f"Pré-inscription refusée pour le {day} : seule la date du jour ({today}) est permise")
    day = today
    path = PREREG_DIR / f"{day}.json"
    if path.exists():
        log.info("Pré-inscription du %s déjà écrite : inchangée", day)
        return json.loads(path.read_text(encoding="utf-8"))
    lat, base = _latest(), _base_rates()
    stocks = _stocks_latest()
    d0 = dt.date.fromisoformat(day)
    content = {
        "date": day, "règles": str(rules()["version"]), "protocole": "research/v1_protocol.md",
        "échéances": {h: (d0.replace(year=d0.year + y)).isoformat() for h, y in HORIZONS.items()},
        "actifs": {k: {"date_données": v.get("date"), "couleur": v.get("color_confirmed"), "cher": v.get("cher"),
                       "cher_tendu": v.get("cher_tendu"), "tendance_cassée": v.get("trend_broken"), "prix": _clean(v.get("price")),
                       "V": _clean(v.get("V")), "rdt_réel_attendu_10a": _clean(v.get("er10")),
                       "fourchette_10a": [_clean(v.get("er10_lo")), _clean(v.get("er10_hi"))],
                       "attentes_historiques_couleur": base.get(k, {}).get(v.get("color_confirmed"), {})}
                   for k, v in lat.items()},
        "hypothèses": [
            "Indices : sur 3 ans, le rendement après un jour vert dépasse celui après un jour orange (1990-2026 : +1 à +3 points par an).",
            "Nasdaq-100 : le drapeau « cher et tendu » (R1) est suivi d'un rendement à 3 ans inférieur à celui des autres jours (1990-2026 : −7,8 points par an contre les autres jours ; non retenu comme règle).",
            "Bitcoin : le rendement à 3 ans après un jour vert dépasse celui après un jour rouge d'au moins 5 points par an.",
            "Actions (indicatif) : à 1 et 3 ans, les sociétés vertes font mieux que les rouges, et les solides mieux que les non solides.",
        ],
        "actions": {"vertes": sorted(s.get("ticker") or k for k, s in stocks.items() if s.get("color_confirmed") == "green"),
                    "rouges": sorted(s.get("ticker") or k for k, s in stocks.items() if s.get("color_confirmed") == "red"),
                    "solides": sorted(s.get("ticker") or k for k, s in stocks.items() if s.get("quality_ok") is True),
                    "prix": {s.get("ticker") or k: _clean(s.get("price")) for k, s in stocks.items()}},
    }
    blob = json.dumps(content, ensure_ascii=False, sort_keys=True, indent=1)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    path.write_text(blob, encoding="utf-8")
    with open(PREREG_DIR / "HASHES.txt", "a", encoding="utf-8") as fh:
        fh.write(f"{day} sha256={digest}\n")
    log.info("Pré-inscription %s : sha256 %s", day, digest)
    return content


def register_monthly() -> dict | None:
    """Une pré-inscription par mois civil : la première exécution du mois l'écrit."""
    month = dt.date.today().strftime("%Y-%m")
    if PREREG_DIR.exists() and any(PREREG_DIR.glob(f"{month}-*.json")):
        log.info("Pré-inscription de %s déjà écrite", month)
        return None
    return register()


# ----------------------------------------------------------------------------------------------
# Tableau de suivi
# ----------------------------------------------------------------------------------------------
def _hashes() -> dict[str, str]:
    hashes = {}
    hp = PREREG_DIR / "HASHES.txt"
    if hp.exists():
        for line in hp.read_text(encoding="utf-8").splitlines():
            if " sha256=" in line:
                k, v = line.split(" sha256=")
                hashes[k.strip()] = v.strip()
    return hashes


def verify_hashes() -> list[dict]:
    """Recalcule l'empreinte de chaque pré-inscription et la compare à celle inscrite le jour même."""
    if not PREREG_DIR.exists():
        return []
    hashes = _hashes()
    out = []
    for path in sorted(PREREG_DIR.glob("20*.json")):
        day = path.stem
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        out.append({"date": day, "inscrite": hashes.get(day), "recalculée": actual, "ok": hashes.get(day) == actual})
    return out


def stock_scores() -> list[dict]:
    """Hypothèse « actions » : rendement médian réalisé (devise de cotation) des sociétés vertes, rouges, solides et autres,
    depuis le prix inscrit jusqu'à l'échéance. Rien n'est calculé avant l'échéance."""
    from .config import ROOT

    sd = ROOT / "data" / "signals" / "stocks"
    # symbole inscrit → fichier de cours (la clé peut différer du symbole : SoftBank « 9984 » / « 9984.T »)
    key_of = {(v.get("ticker") or k): k for k, v in _stocks_latest().items()}
    out = []
    for path in sorted(PREREG_DIR.glob("20*.json")) if PREREG_DIR.exists() else []:
        c = json.loads(path.read_text(encoding="utf-8"))
        a = c.get("actions") or {}
        p0s = {t: p for t, p in (a.get("prix") or {}).items() if p}
        d0 = pd.Timestamp(c["date"])
        groups = {"vertes": set(a.get("vertes", [])), "rouges": set(a.get("rouges", [])), "solides": set(a.get("solides", []))}
        groups["non solides"] = set(p0s) - groups["solides"]
        rec = {"date": c["date"], "effectifs": {g: len(v & set(p0s)) for g, v in groups.items()}}
        for h, due in c["échéances"].items():
            years, rets = HORIZONS[h], {}
            for t in p0s:
                f = sd / f"{key_of.get(t, t)}.parquet"
                if not f.exists():
                    continue
                px = pd.read_parquet(f, columns=["price"])["price"].dropna()
                if px.empty or pd.Timestamp(due) > px.index[-1]:
                    continue
                # les deux bouts dans la même série (cours ajustés des divisions) : une division survenue après l'inscription
                # ne fausse pas le rendement (le prix inscrit, non ajusté, reste dans le fichier pour mémoire)
                p0, p1 = px.asof(d0), px.asof(pd.Timestamp(due))
                if p0 and p1 and p0 == p0 and p1 == p1:
                    rets[t] = (p1 / p0) ** (1 / years) - 1
            rec[h] = None if not rets else {g: _clean(pd.Series([rets[t] for t in v if t in rets]).median()) if any(t in rets for t in v) else None
                                             for g, v in groups.items()}
        out.append(rec)
    return out


def scoreboard() -> list[dict]:
    """Une ligne par pré-inscription et par actif : ce qui était affirmé, et le réalisé si l'échéance est passée."""
    from .signals import load_signals

    if not PREREG_DIR.exists():
        return []
    hashes = _hashes()
    verified = {v["date"]: v["ok"] for v in verify_hashes()}
    out = []
    prices = {}
    for path in sorted(PREREG_DIR.glob("20*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        for asset, a in c["actifs"].items():
            if asset not in prices:
                try:
                    prices[asset] = load_signals(asset)["price"]
                except Exception:
                    prices[asset] = None
            px = prices[asset]
            rec = {"date": c["date"], "empreinte": hashes.get(c["date"], "")[:12], "empreinte_ok": verified.get(c["date"], False),
                   "actif": asset, "couleur": a["couleur"],
                   "cher": a.get("cher"), "attentes": a.get("attentes_historiques_couleur", {})}
            for h, due in c["échéances"].items():
                if px is None or pd.Timestamp(due) > px.index[-1]:
                    rec[h] = None
                    continue
                p0 = px.asof(pd.Timestamp(a["date_données"] or c["date"]))
                p1 = px.asof(pd.Timestamp(due))
                years = HORIZONS[h]
                rec[h] = _clean((p1 / p0) ** (1 / years) - 1) if p0 and p1 else None
            out.append(rec)
    return out
