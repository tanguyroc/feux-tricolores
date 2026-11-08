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
        df["trend_broken"] = store.as_of(store.make_series(broken_m.index, broken_m.astype(float).to_numpy()), px.index).fillna(0.0).astype(bool)
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


def simple_sentence(key: str, row: pd.Series) -> str:
    r = rules()["themes"]
    name = r["assets"][key]["name"]
    up = f"{100 * row['runup_24m']:+.0f} % en deux ans"
    if bool(row["gsy"]) and bool(row["runup_alert"]):
        return (f"{name} : {up}, et la hausse s'accélère. Dans l'étude de référence, une chute d'au moins 40 % a suivi ce type de hausse "
                f"dans environ 80 % des cas. Aucun renfort thématique, pas de levier sur ce thème.")
    if bool(row["gsy"]):
        return (f"{name} : {up}, et la hausse s'accélère. Dans l'étude de référence, une chute d'au moins 40 % a suivi ce type de hausse "
                f"dans environ un cas sur deux. Prudence sur tout renfort thématique.")
    if bool(row["extended"]):
        return f"{name} : {up} ; les cours sont très au-dessus de leur moyenne des 200 jours (plus que 90 % du temps). Pas de renfort précipité."
    if bool(row["trend_broken"]):
        return f"{name} : {up} ; tendance cassée (dernier mois sous la moyenne des 10 mois), à {100 * row['drawdown']:.0f} % sous le plus haut. Pas de levier thématique."
    return f"{name} : {up}, rien d'extrême."
