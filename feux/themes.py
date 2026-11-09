"""Drapeaux de bulle sectorielle : le critère de Greenwood-Shleifer-You (« Bubbles for Fama », JFE 2019) a été établi
sur des SECTEURS, c'est donc ici qu'il est le plus légitime. Pas de couleur (pas de valorisation) : des drapeaux."""
from __future__ import annotations

import json
import logging

import pandas as pd

from . import indicators as ind
from . import store
from .config import DOCS_DIR, rules
from .signals import SIGNALS_DIR

log = logging.getLogger("feux.themes")
TD = 252


def compute_all() -> dict[str, pd.DataFrame]:
    r = rules()
    t = r["themes"]
    w = r["windows"]
    out = {}
    for key, spec in t["assets"].items():
        if not store.exists(f"px_theme_{key}"):
            log.warning("prix absents pour le thème %s", key)
            continue
        px = store.to_indexed(store.load(f"px_theme_{key}"))
        df = pd.DataFrame({"price": px})
        g = t["gsy"]
        df["runup_24m"] = ind.momentum(px, 21 * g["runup_months"])
        df["gsy"] = ind.gsy_flag(px, 21 * g["runup_months"], 21 * g["accel_short_months"], g["runup_min"])
        df["runup_alert"] = df["runup_24m"] >= t["runup_alert_min"]
        df["gap_ma200"] = ind.gap_to_ma(px, 200)
        df["gap_ma200_pct"] = ind.rolling_pct(df["gap_ma200"], TD * w["pct_years"], TD * w["pct_min_years_fast"])
        df["extended"] = df["gap_ma200_pct"] >= t["extension_red_min"]
        df["drawdown"] = ind.drawdown(px)
        broken_m = ind.sma_month_flag(px, t["leverage_flag"]["sma_months"])
        # même décalage d'un jour que les indices : la clôture mensuelle n'est connue qu'après la séance (v1.0.1)
        df["trend_broken"] = store.as_of(store.make_series(broken_m.index, broken_m.astype(float).to_numpy(), lag=pd.Timedelta(days=1)),
                                         px.index).fillna(0.0).astype(bool)
        df["asset"] = key
        out[key] = df
        last = df.iloc[-1]
        log.info("%-9s GSY=%s hausse 2 ans=%+.0f %% extension p%.0f tendance %s", key, last["gsy"], 100 * last["runup_24m"],
                 last["gap_ma200_pct"] if last["gap_ma200_pct"] == last["gap_ma200_pct"] else float("nan"), "cassée" if last["trend_broken"] else "OK")
    return out


def save_all(res: dict[str, pd.DataFrame]) -> None:
    (SIGNALS_DIR / "themes").mkdir(exist_ok=True)
    latest = {}
    for key, df in res.items():
        df.to_parquet(SIGNALS_DIR / "themes" / f"{key}.parquet")
        last = df.iloc[-1]
        latest[key] = {k: (None if isinstance(v, float) and v != v else (v.item() if hasattr(v, "item") else v)) for k, v in last.items() if k != "asset"}
        latest[key]["date"] = str(df.index[-1].date())
    (DOCS_DIR / "themes_latest.json").write_text(json.dumps(latest, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


def load_all() -> dict[str, pd.DataFrame]:
    d = SIGNALS_DIR / "themes"
    return {p.stem: pd.read_parquet(p) for p in sorted(d.glob("*.parquet"))} if d.exists() else {}


def simple_sentence(key: str, row: pd.Series, valuation: dict | None = None) -> str:
    r = rules()["themes"]
    name = r["assets"][key]["name"]
    up = f"{100 * row['runup_24m']:+.0f} % en deux ans"
    val = ""
    if valuation and valuation.get("v_median") is not None:
        val = f" Valorisation médiane de ses {valuation['n']} grandes sociétés : {v_label(valuation['v_median'])} (p{valuation['v_median']:.0f})."
    if bool(row["gsy"]) and bool(row["runup_alert"]):
        return (f"{name} : {up}, et la hausse s'accélère. Dans l'étude de référence, une chute d'au moins 40 % a suivi ce type de hausse "
                f"dans environ 80 % des cas. Aucun renfort, pas de levier sur ce secteur.{val}")
    if bool(row["gsy"]):
        return (f"{name} : {up}, et la hausse s'accélère. Dans l'étude de référence, une chute d'au moins 40 % a suivi ce type de hausse "
                f"dans environ un cas sur deux. Prudence sur tout renfort.{val}")
    if bool(row["extended"]):
        return f"{name} : {up} ; les cours sont très au-dessus de leur moyenne des 200 jours (plus que 90 % du temps). Pas de renfort précipité.{val}"
    if bool(row["trend_broken"]):
        return f"{name} : {up} ; tendance cassée (dernier mois sous la moyenne des 10 mois), à {100 * row['drawdown']:.0f} % sous le plus haut. Pas de levier.{val}"
    return f"{name} : {up}, rien d'extrême côté prix.{val}"


def v_label(v: float) -> str:
    """Cinq paliers de lecture d'un percentile de valorisation (le feu, lui, reste à trois couleurs)."""
    if v is None or v != v:
        return "n.d."
    if v <= 20:
        return "très bon marché"
    if v <= 40:
        return "bon marché"
    if v <= 60:
        return "dans sa moyenne"
    if v <= 80:
        return "cher"
    return "très cher"


def overlay(stocks_latest: dict) -> list[dict]:
    """Lignes « secteurs et thèmes » prêtes pour l'application : drapeaux de prix de l'ETF + valorisation médiane des
    sociétés du Top 100 du secteur + couleur (mêmes règles de conjonction que les indices). Non backtesté : lecture de contexte."""
    r = rules()["themes"]
    res = load_all()
    rows = []
    for key, spec in r["assets"].items():
        df = res.get(key)
        if df is None or df.empty:
            continue
        row = df.iloc[-1]
        valuation = None
        if spec.get("kind") == "sector":
            vs = [s["V"] for s in stocks_latest.values()
                  if s.get("kind") == "operating" and s.get("V") is not None and s.get("sector") == spec.get("gics")]
            n = len(vs)
            med = float(pd.Series(vs).median()) if n >= int(r["sector_min_members"]) else None
            members = sorted([s for s in stocks_latest.values() if s.get("sector") == spec.get("gics")], key=lambda s: (s.get("rank") or 999))
            valuation = {"n": n, "v_median": med, "members": [{"ticker": s.get("ticker"), "name": s.get("name"), "V": s.get("V"),
                                                                  "color": s.get("color_confirmed")} for s in members]}
        # v1.0 : plus de couleur sectorielle (bruit : tous orange, trois secteurs jamais calculables, ETF américain contre membres
        # mondiaux). Drapeaux de prix de l'ETF et valorisation médiane des membres restent affichés comme contexte.
        color = "none"
        rows.append({"key": key, "name": spec["name"], "kind": spec.get("kind", "theme"), "ticker": spec["ticker"], "gics": spec.get("gics"),
                     "color": color, "sentence": simple_sentence(key, row, valuation),
                     "runup_24m": float(row["runup_24m"]), "gsy": bool(row["gsy"]), "extended": bool(row["extended"]),
                     "gap_ma200": float(row["gap_ma200"]), "gap_pct": None if pd.isna(row["gap_ma200_pct"]) else float(row["gap_ma200_pct"]),
                     "trend_broken": bool(row["trend_broken"]), "drawdown": float(row["drawdown"]), "date": str(df.index[-1].date()),
                     "valuation": valuation})
    return rows
