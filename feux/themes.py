"""Secteurs, thèmes et zones géographiques.

Drapeaux de prix : le critère de Greenwood-Shleifer-You (« Bubbles for Fama », JFE 2019) a été établi sur des SECTEURS.
Valorisation contre son passé : une INFORMATION, pas un feu (v1.1). Secteurs avec au moins 5 sociétés du Top 100 → médiane
de leurs valorisations (chacune contre son propre passé) ; sinon → prix de l'ETF / moyenne de ses dividendes RÉELS sur 10 ans
(un « CAPE » fait avec les dividendes), contre son propre passé. Testée sur 16 pays de 1870 à 2020 (research/zones_test_protocol.md),
la mesure par les dividendes ne passe pas le seuil fixé d'avance pour mériter un feu (v1.0.2 : feu indicatif vert/orange).
Pas assez d'historique ou dividendes trop faibles → valorisation non mesurable, avec la raison."""
from __future__ import annotations

import json
import logging

import numpy as np
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
        _pd10(df, key, px, t.get("valuation", {}))
        df["asset"] = key
        out[key] = df
        last = df.iloc[-1]
        log.info("%-9s GSY=%s hausse 2 ans=%+.0f %% extension p%.0f tendance %s", key, last["gsy"], 100 * last["runup_24m"],
                 last["gap_ma200_pct"] if last["gap_ma200_pct"] == last["gap_ma200_pct"] else float("nan"), "cassée" if last["trend_broken"] else "OK")
    return out


def _pd10(df: pd.DataFrame, key: str, px: pd.Series, vz: dict) -> None:
    """Prix / moyenne des dividendes réels sur 10 ans (en dollars constants, indice des prix américain) et son percentile
    contre son propre passé (références de fin de mois, au moins 5 ans)."""
    df["pd10"] = np.nan
    df["avg_yield_10y"] = np.nan
    df["V_pd10"] = np.nan
    px = px[~px.index.duplicated(keep="last")]
    if not vz or not store.exists(f"div_theme_{key}"):
        return
    div = store.to_indexed(store.load(f"div_theme_{key}"))
    div = div[div > 0]
    if div.empty:
        return
    cpi = store.to_indexed(store.load("shiller_CPI"))

    def at(series, idx):
        series = series[~series.index.duplicated(keep="last")].sort_index()
        return series.reindex(series.index.union(idx.unique())).ffill().reindex(idx)

    years = int(vz.get("pd10_years", 10))
    real = div / at(cpi, div.index).to_numpy()
    cum = real.cumsum()
    lagged = px.index - pd.DateOffset(years=years)
    s10 = at(cum, px.index).fillna(0.0).to_numpy() - at(cum, lagged).fillna(0.0).to_numpy()
    pd10 = pd.Series((px / at(cpi, px.index)).to_numpy() * years / np.where(s10 > 0, s10, np.nan), index=px.index)
    pd10[(px.index - div.index[0]) < pd.Timedelta(days=round(365.25 * years))] = np.nan     # 10 années pleines de dividendes
    df["pd10"] = pd10
    df["avg_yield_10y"] = 1.0 / pd10
    ref = pd10.resample("ME").last().dropna()
    df["V_pd10"] = ind.pct_against_reference(pd10, ref, 10 ** 7, int(vz.get("pd10_min_history_months", 60)))
    df["div_since"] = str(div.index[0].date())     # colonnes (les attributs ne survivent pas toujours au parquet)
    df["div_last"] = str(div.index[-1].date())


def _members_v(keys: list[str], min_n: int) -> pd.Series:
    """Médiane, à chaque date, des V des sociétés du secteur (chacune contre son propre passé), si au moins `min_n`."""
    d = SIGNALS_DIR / "stocks"
    cols = {}
    for k in keys:
        f = d / f"{k.replace('/', '_')}.parquet"
        if f.exists():
            v = pd.read_parquet(f, columns=["V"])["V"]
            cols[k] = v[~v.index.duplicated()]
    if not cols:
        return pd.Series(dtype=float)
    panel = pd.concat(cols, axis=1).sort_index().ffill(limit=5)
    med = panel.median(axis=1, skipna=True)
    return med.where(panel.notna().sum(axis=1) >= min_n)


def valuation_light(key: str, spec: dict, df: pd.DataFrame, members: list[tuple[str, dict]]) -> dict:
    """Valorisation d'un secteur, thème ou zone contre son passé (information depuis la v1.1), avec la mesure employée ou la
    raison de son absence."""
    from .signals import confirmed_color

    vz = rules()["themes"].get("valuation", {})
    days = int(rules().get("confirmation_days", 5))
    out = {"color": "none", "color_confirmed": "none", "V": None, "measure": None, "reason": None, "cher": False, "since": None}
    series, measure = None, None
    valued = [(k, m) for k, m in members if m.get("kind") == "operating" and m.get("V") is not None]
    if spec.get("measure") == "cape_sp500":
        # États-Unis : la mesure de référence (CAPE de Shiller depuis 1881, celle du feu S&P 500) ; P/D10 rappelé à titre indicatif
        from .signals import load_signals
        series = load_signals("sp500")["V"]
        measure = "CAPE de Shiller du S&P 500 contre tous les mois depuis 1881 (la mesure du feu S&P 500, plus fiable que les dividendes)"
        if "V_pd10" in df and df["V_pd10"].notna().any():
            ref0 = df["pd10"].first_valid_index()
            yld = f"{100 * df['avg_yield_10y'].iloc[-1]:.1f}".replace(".", ",")
            measure += (f" ; par les dividendes comme les autres zones : {df['V_pd10'].dropna().iloc[-1]:.0f}e percentile depuis {ref0.year}, "
                        f"à titre indicatif (dividendes de {yld} %/an, réduits par les rachats d'actions)")
    elif len(valued) >= int(vz.get("members_min", 5)):
        series = _members_v([k for k, _ in valued], int(vz.get("members_min", 5)))
        measure = (f"médiane des {len(valued)} sociétés du Top 100 du {'secteur' if spec.get('kind') == 'sector' else 'thème'}, "
                   "chacune contre ses dix dernières années (EV/EBIT et flux libre, ou P/E et P/B)")
    elif "div_last" in df and isinstance(df["div_last"].iloc[-1], str) and (df.index[-1] - pd.Timestamp(df["div_last"].iloc[-1])).days > 400:
        out["reason"] = (f"aucun dividende publié depuis le {pd.Timestamp(df['div_last'].iloc[-1]):%d/%m/%Y} (plus de 13 mois) : "
                         "donnée manquante ou distribution suspendue, valorisation non mesurable")
    elif "V_pd10" in df and df["V_pd10"].notna().any():
        y = df["avg_yield_10y"]
        series = df["V_pd10"].where(y >= float(vz.get("min_avg_yield", 0.01)))
        first = df["V_pd10"].first_valid_index()
        ref0 = df["pd10"].first_valid_index()
        measure = (f"prix / dividendes réels moyens sur 10 ans de l'ETF {spec['ticker']}, contre son propre passé "
                   f"(comparé depuis {ref0.year if ref0 is not None else '—'}, soit {((df.index[-1] - ref0).days / 365.25) if ref0 is not None else 0:.0f} ans)")
        if pd.isna(series.iloc[-1]) and pd.notna(y.iloc[-1]):
            few = f"{len(valued)} société{'s' if len(valued) > 1 else ''} du Top 100 seulement et " if members else ""
            yld = f"{100 * y.iloc[-1]:.1f}".replace(".", ",")
            out["reason"] = f"{few}dividendes trop faibles ({yld} %/an en moyenne sur 10 ans) pour mesurer une valorisation"
    if series is not None:
        series = series[~series.index.duplicated()].sort_index()
        series = series.reindex(series.index.union(df.index)).ffill(limit=5).reindex(df.index)
    if series is None or series.dropna().empty or pd.isna(series.iloc[-1]):
        if out["reason"] is None:
            since = df["div_since"].iloc[-1] if "div_since" in df and isinstance(df["div_since"].iloc[-1], str) else None
            if spec.get("kind") == "sector" and not since:
                out["reason"] = f"moins de {vz.get('members_min', 5)} sociétés du Top 100 et pas de dividendes exploitables"
            elif since:
                out["reason"] = (f"historique insuffisant : il faut 10 ans de dividendes puis 5 ans de comparaison "
                                 f"(dividendes depuis {since[:4]})")
            elif spec.get("kind") == "sector":
                out["reason"] = f"moins de {vz.get('members_min', 5)} sociétés du Top 100 valorisées ({len(valued)})"
            else:
                out["reason"] = "pas de dividendes publiés pour cet ETF : valorisation non mesurable"
        out["measure"] = measure
        return out
    v = series
    last_v = float(v.iloc[-1])
    if vz.get("status") == "information":
        # v1.1 : un palier de lecture (très bon marché … très cher), sans couleur de feu ; « depuis » = depuis quand ce palier dure
        band = v.map(lambda x: v_label(x) if x == x else None)
        conf = confirmed_color(band.fillna("n.d."), days)
        changes = conf[conf != conf.iloc[-1]]
        out.update({"color": "info", "color_confirmed": "info", "V": last_v, "band": conf.iloc[-1], "measure": measure,
                    "cher": last_v >= float(vz.get("cher_min", 80)),
                    "since": str((conf.index[0] if changes.empty else conf.index[conf.index.get_loc(changes.index[-1]) + 1]).date())})
        return out
    color = pd.Series("none", index=df.index, dtype=object)          # v1.0.2 (feu indicatif), conservé pour mémoire
    color[v.notna()] = "orange"
    color[v <= float(vz.get("green_max", 40))] = "green"
    conf = confirmed_color(color, days)
    conf[color == "none"] = "none"
    changes = conf[conf != conf.iloc[-1]]
    out.update({"color": color.iloc[-1], "color_confirmed": conf.iloc[-1], "V": last_v, "measure": measure,
                "cher": last_v >= float(vz.get("cher_min", 80)),
                "since": str((conf.index[0] if changes.empty else conf.index[conf.index.get_loc(changes.index[-1]) + 1]).date())})
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
            members_kv = [(k, s) for k, s in stocks_latest.items() if s.get("sector") == spec.get("gics")]
        elif spec.get("industries"):
            members_kv = [(k, s) for k, s in stocks_latest.items() if s.get("industry") in spec["industries"]]
        else:
            members_kv = []
        light = valuation_light(key, spec, df, members_kv)
        if members_kv:
            vs = [s["V"] for _, s in members_kv if s.get("kind") == "operating" and s.get("V") is not None]
            n = len(vs)
            med = float(pd.Series(vs).median()) if n >= int(r["sector_min_members"]) else None
            members = sorted([s for _, s in members_kv], key=lambda s: (s.get("rank") or 999))
            valuation = {"n": n, "v_median": med, "members": [{"ticker": s.get("ticker"), "name": s.get("name"), "V": s.get("V"),
                                                                  "color": s.get("color_confirmed")} for s in members]}
        # v1.1 : valorisation en information (« info ») ; « none » = non mesurable, raison affichée
        color = light["color_confirmed"]
        rows.append({"key": key, "name": spec["name"], "kind": spec.get("kind", "theme"), "ticker": spec["ticker"], "gics": spec.get("gics"),
                     "color": color, "light": light, "sentence": simple_sentence(key, row, valuation if light["measure"] is None else None),
                     "note": spec.get("note"),
                     "pd10": None if pd.isna(row.get("pd10", np.nan)) else float(row["pd10"]),
                     "avg_yield_10y": None if pd.isna(row.get("avg_yield_10y", np.nan)) else float(row["avg_yield_10y"]),
                     "runup_24m": float(row["runup_24m"]), "gsy": bool(row["gsy"]), "extended": bool(row["extended"]),
                     "gap_ma200": float(row["gap_ma200"]), "gap_pct": None if pd.isna(row["gap_ma200_pct"]) else float(row["gap_ma200_pct"]),
                     "trend_broken": bool(row["trend_broken"]), "drawdown": float(row["drawdown"]), "date": str(df.index[-1].date()),
                     "valuation": valuation})
    return rows
