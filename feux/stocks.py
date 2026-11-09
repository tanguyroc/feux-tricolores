"""Module actions : univers Top 100 mondial (+ compléments de stocks.yaml).

Pour chaque société :
- toujours : extension de prix (écart MM200 en percentile 10 ans), critère de bulle GSY, tendance, baisse depuis le plus haut ;
- si ses comptes sont dans EDGAR (CIK) : valorisation point-in-time (EV/EBIT, P/FCF en percentile 10 ans), DCF inversé,
  filtre qualité éliminatoire, couleur. Sinon : « prix seul », jamais rouge ni vert (pas de valorisation) ;
- proxys crypto : suivent le feu Bitcoin et leur propre tendance.
Les prix sont convertis dans la devise des comptes quand elles diffèrent (ex. Shell : cours en pence, comptes en dollars).
"""
from __future__ import annotations

import json
import logging
import time

import numpy as np
import pandas as pd
import yaml

from . import indicators as ind
from . import store
from .config import DOCS_DIR, ROOT, rules
from .loaders import edgar, log as loader_log, yahoo
from .signals import SIGNALS_DIR, confirmed_color, load_signals

log = logging.getLogger("feux.stocks")
STOCKS_PATH = ROOT / "stocks.yaml"
TD = 252
_FX_CACHE: dict[str, pd.Series] = {}


def extras() -> dict:
    """Compléments / surcharges de stocks.yaml (type crypto_proxy, valeurs hors Top 100...)."""
    if not STOCKS_PATH.exists():
        return {}
    with open(STOCKS_PATH, encoding="utf-8") as fh:
        wl = yaml.safe_load(fh).get("stocks", {}) or {}
    return {str(k): v for k, v in wl.items()}


# ----------------------------------------------------------------------------------------------
MAX_AGE_DAYS = 400          # au-delà, une valeur comptable n'est plus reportée : un concept abandonné ne fige pas le ratio
MAX_AGE_DAYS_ANNUAL = 730   # déposants annuels (20-F) : un exercice reste lu jusqu'à deux ans (TSMC : le 20-F 2025 n'est pas encore dans l'API)
MAX_AGE_DAYS_SHARES = 800   # nombre d'actions : varie lentement (rachats ~1-3 %/an), publié parfois une fois l'an


def _asof(df: pd.DataFrame, cal: pd.DatetimeIndex, max_age_days: int = MAX_AGE_DAYS) -> pd.Series:
    """Dernière valeur publiée à chaque date du calendrier, puis oubliée si sa période de référence date de plus de
    `max_age_days` (ex. KLA n'a plus publié de « résultat d'exploitation » depuis 2015 : sans ce garde-fou la valeur
    de 2015 aurait été reportée jusqu'à aujourd'hui)."""
    if df is None or df.empty:
        return pd.Series(np.nan, index=cal)
    s = store.make_series(df["end"], df["val"], available_dates=df["filed"])
    s = s.sort_values(["available_date", "ref_date"]).drop_duplicates("available_date", keep="last")
    v = store.as_of(s, cal)
    ref = store.as_of(s.assign(value=pd.to_datetime(s["ref_date"]).astype("datetime64[ns]").astype("int64").astype("float64")), cal)
    age_days = (pd.Series(pd.DatetimeIndex(cal).astype("datetime64[ns]").astype("int64").astype("float64"), index=cal) - ref) / 86_400e9
    return v.where(age_days <= max_age_days)


def split_adjust_shares(sh: pd.DataFrame, splits: list[tuple[pd.Timestamp, float]]) -> pd.DataFrame:
    """Ramène chaque nombre d'actions publié (période `end`) à la base actuelle : × rapport de chaque division postérieure."""
    out = sh.copy()
    ends = pd.to_datetime(out["end"]).to_numpy()
    factor = np.ones(len(out))
    for d, ratio in splits:
        factor = factor * np.where(ends < np.datetime64(pd.Timestamp(d)), ratio, 1.0)
    out["val"] = out["val"].to_numpy() * factor
    out.attrs.update(sh.attrs)
    return out


def _ref_age_days(df: pd.DataFrame, cal: pd.DatetimeIndex) -> pd.Series:
    """Âge (jours) de la dernière période comptable publiée, à chaque date du calendrier."""
    if df is None or df.empty:
        return pd.Series(np.nan, index=cal)
    s = store.make_series(df["end"], df["val"], available_dates=df["filed"])
    s = s.sort_values(["available_date", "ref_date"]).drop_duplicates("available_date", keep="last")
    ref = store.as_of(s.assign(value=pd.to_datetime(s["ref_date"]).astype("datetime64[ns]").astype("int64").astype("float64")), cal)
    return (pd.Series(pd.DatetimeIndex(cal).astype("datetime64[ns]").astype("int64").astype("float64"), index=cal) - ref) / 86_400e9


# Industries GICS pour lesquelles EV, EBIT et FCF n'ont pas de sens : P/E, P/B et rentabilité des fonds propres.
# « Financial Services » (Visa, Mastercard, Berkshire) reste en mode industriel : réseaux de paiement = sociétés d'exploitation à FCF massif.
FINANCIAL_INDUSTRIES = {"Banks", "Capital Markets", "Consumer Finance", "Insurance", "Diversified Financial Services",
                        "Thrifts & Mortgage Finance", "Mortgage Real Estate Investment Trusts (Reits)"}


def _mode(spec: dict, f: dict) -> str:
    sector, industry = spec.get("sector") or "", spec.get("industry") or ""
    if sector == "Real Estate" or "Reit" in industry or "REIT" in industry:
        return "reit"
    if industry in FINANCIAL_INDUSTRIES or (sector == "Financials" and industry != "Financial Services" and (f.get("ebit") is None or len(f["ebit"]) == 0)):
        return "financial"
    return "industrial"


def _mean_years(s: pd.Series, years: float, min_years: float) -> pd.Series:
    """Moyenne glissante sur `years` années de bourse (au moins `min_years` de valeurs ; lacunes ≤ 6 mois comblées)."""
    return s.ffill(limit=TD // 2).rolling(int(TD * years), min_periods=int(TD * min_years)).mean()


def implied_growth(ev: float, fcf: float, wacc: float, g_term: float, years: int) -> float:
    """Croissance annuelle du FCF sur `years` ans qui égalise la valeur actuelle des flux à l'EV (bissection)."""
    if not (fcf > 0 and ev > 0):
        return np.nan

    def pv(g):
        flows = fcf * (1 + g) ** np.arange(1, years + 1)
        disc = (1 + wacc) ** np.arange(1, years + 1)
        terminal = flows[-1] * (1 + g_term) / (wacc - g_term) / disc[-1]
        return float((flows / disc).sum() + terminal)

    lo, hi = -0.5, 1.5
    if pv(lo) > ev:
        return lo
    if pv(hi) < ev:
        return hi
    for _ in range(60):
        mid = (lo + hi) / 2
        if pv(mid) < ev:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def fx_series(from_ccy: str, to_ccy: str, cal: pd.DatetimeIndex) -> pd.Series:
    """Taux de change quotidien from->to (Yahoo « EURUSD=X »), avec gestion des pence (GBp)."""
    scale = 1.0
    if from_ccy == "GBp":
        from_ccy, scale = "GBP", 0.01
    if from_ccy == to_ccy:
        return pd.Series(scale, index=cal)
    key = f"{from_ccy}{to_ccy}=X"
    if key not in _FX_CACHE:
        _FX_CACHE[key] = yahoo.fetch_close(key)
        time.sleep(0.5)
    fx = _FX_CACHE[key].reindex(_FX_CACHE[key].index.union(cal)).ffill().reindex(cal)
    return fx * scale


def price_block(px: pd.Series) -> pd.DataFrame:
    r = rules()["stocks"]
    w, mn = TD * r["valuation"]["pct_years"], TD * r["valuation"]["pct_min_years"]
    g = r["extension"]["gsy"]
    df = pd.DataFrame({"price": px})
    df["gap_ma200"] = ind.gap_to_ma(px, 200)
    df["gap_ma200_pct"] = ind.rolling_pct(df["gap_ma200"], w, mn)
    df["runup_24m"] = ind.momentum(px, 21 * g["runup_months"])
    df["gsy"] = ind.gsy_flag(px, 21 * g["runup_months"], 21 * g["accel_short_months"], g["runup_min"])
    df["trend_broken"] = (df["gap_ma200"] < 0).fillna(False)
    df["drawdown"] = ind.drawdown(px)
    df["mom_12m"] = ind.momentum(px, TD)
    return df


def analyse_operating(key: str, spec: dict) -> pd.DataFrame:
    r = rules()["stocks"]
    px, px_ccy = yahoo.fetch_close_meta(spec["ticker"])
    cal = px.index
    f = edgar.fundamentals(int(spec["cik"]), tuple(int(c) for c in (spec.get("extra_ciks") or [])))
    df = price_block(px)
    shares_source = f["shares"].attrs.get("concept") if len(f["shares"]) else None
    # Les prix Yahoo sont ajustés des divisions d'actions, pas les nombres d'actions publiés à la SEC (première publication) :
    # chaque observation antérieure à une division est ramenée à la base actuelle (sinon la capitalisation historique est
    # 10 ou 20 fois trop petite avant la division, et la valorisation paraît artificiellement chère contre son passé).
    splits = yahoo.splits(spec["ticker"])
    if splits and len(f["shares"]):
        f["shares"] = split_adjust_shares(f["shares"], splits)
    split_list = [(str(d.date()), r) for d, r in splits]
    if f.get("shares_stale") and len(f.get("public_float", [])) >= 3:
        # actions multi-classes sans nombre d'actions exploitable (Visa, Berkshire) : actions ≈ flottant déclaré / cours du jour du flottant
        pf = f["public_float"].copy()
        pf["px"] = px.reindex(pd.DatetimeIndex(pf["end"]), method="ffill").to_numpy()
        pf = pf.dropna(subset=["px"])
        pf["val"] = pf["val"] / pf["px"]
        f["shares"] = pf[["end", "filed", "val"]].reset_index(drop=True)
        f["shares"].attrs.update({"concept": "flottant déclaré / cours (approximation)", "unit": "shares"})
        shares_source = f["shares"].attrs["concept"]
    unit = next((v.attrs.get("unit") for k, v in f.items() if hasattr(v, "attrs") and k != "public_float" and v.attrs.get("unit") and v.attrs.get("unit") != "shares"), px_ccy)
    df["price_in_accounts_ccy"] = px * fx_series(px_ccy, unit, cal) if unit and px_ccy and unit != px_ccy else px
    for k in ("revenue", "ebit", "net_income", "cfo", "capex", "da", "cash", "st_investments", "debt_lt", "debt_st", "equity", "shares",
              "assets", "pretax", "interest", "sbc", "dividends", "buybacks", "issuance", "gross_profit", "cost_of_revenue"):
        # déposants de 20-F (valeurs annuelles publiées 3 à 4 mois après la clôture) : tolérance plus longue avant d'oublier une valeur
        annual = f.get(k) is not None and bool(getattr(f[k], "attrs", {}).get("annual_only"))
        age = MAX_AGE_DAYS_SHARES if k == "shares" else MAX_AGE_DAYS_ANNUAL if annual else MAX_AGE_DAYS
        df[k] = _asof(f.get(k), cal, max_age_days=age)
    accounts_as_of = None if f["net_income"].empty else str(pd.Timestamp(f["net_income"]["end"].max()).date())
    df["accounts_age_days"] = _ref_age_days(f["net_income"], cal)
    # résultat d'exploitation absent ou plus publié (pétrole, pharma, banques, KLA depuis 2015) : résultat avant impôt + intérêts
    ebit_source = "résultat d'exploitation"
    if pd.isna(df["ebit"].iloc[-1]) and df["pretax"].notna().any():
        # on comble aussi les trous intermédiaires (concept abandonné puis repris) pour garder des moyennes calculables
        df["ebit"] = df["ebit"].fillna(df["pretax"] + df["interest"].fillna(0.0))
        ebit_source = "résultat avant impôt + intérêts (approximation)"
    has_capex = f.get("capex") is not None and len(f["capex"]) > 0
    df["fcf_gross"] = df["cfo"] - (df["capex"].ffill() if has_capex else np.nan)   # sans capex connu : FCF inconnu (pas CFO)
    # v1.0 : la rémunération en actions est un coût réel (Buffett, Mauboussin) : FCF = CFO − capex − SBC
    sbc_known = f.get("sbc") is not None and len(f["sbc"]) > 0
    df["fcf"] = df["fcf_gross"] - (df["sbc"].fillna(0.0) if sbc_known else 0.0)
    df["debt"] = df["debt_lt"].fillna(0.0) + df["debt_st"].fillna(0.0)
    df["liquidity"] = df["cash"].fillna(0.0) + df["st_investments"].fillna(0.0)
    df["mcap"] = df["price_in_accounts_ccy"] * df["shares"]
    # garde-fou : un nombre d'actions exprimé en ADS ou dans une autre unité rend la capitalisation absurde
    last_rev, last_ni = df["revenue"].iloc[-1], df["net_income"].iloc[-1]
    shares_ok = not (pd.notna(last_rev) and pd.notna(last_ni) and last_ni > 0 and df["mcap"].iloc[-1] < 0.2 * last_rev)
    if not shares_ok:
        df["mcap"] = np.nan
    df["ev"] = df["mcap"] + df["debt"] - df["liquidity"]
    # contexte v1.0 : retours aux actionnaires, dilution, qualité des résultats, marge brute
    df["dividend_yield"] = (df["dividends"].abs() / df["mcap"]).where(df["mcap"] > 0)
    df["net_buyback_yield"] = ((df["buybacks"].abs().fillna(0.0) - df["issuance"].abs().fillna(0.0)) / df["mcap"]).where((df["mcap"] > 0) & df["buybacks"].notna())
    df["shareholder_yield"] = df["dividend_yield"].fillna(0.0) + df["net_buyback_yield"].fillna(0.0)
    df.loc[df["dividends"].isna() & df["buybacks"].isna(), "shareholder_yield"] = np.nan
    df["dilution_3y"] = df["shares"] / df["shares"].shift(3 * TD) - 1.0
    df["accruals"] = ((df["net_income"] - df["cfo"]) / df["assets"]).where(df["assets"] > 0)
    gp = df["gross_profit"].where(df["gross_profit"].notna(), df["revenue"] - df["cost_of_revenue"])
    df["gross_margin"] = (gp / df["revenue"]).where(df["revenue"] > 0)
    df["gross_profitability"] = (gp / df["assets"]).where(df["assets"] > 0)
    df["sbc_to_revenue"] = (df["sbc"] / df["revenue"]).where(df["revenue"] > 0)
    w, mn = TD * r["valuation"]["pct_years"], TD * r["valuation"]["pct_min_years"]
    q = r["quality"]
    ay, amy = q.get("avg_years", 5), q.get("avg_min_years", 3)
    mode = _mode(spec, f)
    fails = pd.DataFrame(index=cal)   # une colonne par test de solidité : True = test échoué
    for c in ("ev_ebit", "ev_ebit_pct", "p_fcf", "p_fcf_pct", "roic", "fcf_ni", "nd_ebitda", "roic_avg", "fcf_ni_avg", "nd_ebitda_avg",
              "pe", "pb", "pe_pct", "pb_pct", "roe", "roe_avg", "da_known"):
        df[c] = np.nan
    if mode in ("financial", "reit"):
        # banques, assureurs, foncières : EV et FCF n'ont pas de sens → P/E et P/B contre leur propre historique
        df["pe"] = (df["mcap"] / df["net_income"]).where(df["net_income"] > 0)
        df["pb"] = (df["mcap"] / df["equity"]).where(df["equity"] > 0)
        df["pe_pct"] = ind.rolling_pct(df["pe"], w, mn)
        df["pb_pct"] = ind.rolling_pct(df["pb"], w, mn)
        df["V"] = df[["pe_pct", "pb_pct"]].median(axis=1, skipna=True)
        df["roe"] = (df["net_income"] / df["equity"]).where(df["equity"] > 0)
        df["roe_avg"] = _mean_years(df["roe"], ay, amy)
        if mode == "financial":
            fails["rentabilité"] = ~(df["roe_avg"] >= q["roic_min"])
            df["quality_ok"] = ~fails.any(axis=1) & df["roe_avg"].notna()
        else:
            # foncières : la grille (ROIC, FCF, dette/EBITDA) ne s'applique pas ; pas de test, donc jamais vertes
            df["quality_ok"] = np.nan
    else:
        df["ev_ebit"] = (df["ev"] / df["ebit"]).where(df["ebit"] > 0)
        df["p_fcf"] = (df["mcap"] / df["fcf"]).where(df["fcf"] > 0)
        df["ev_ebit_pct"] = ind.rolling_pct(df["ev_ebit"], w, mn)
        df["p_fcf_pct"] = ind.rolling_pct(df["p_fcf"], w, mn)
        df["V"] = df[["ev_ebit_pct", "p_fcf_pct"]].median(axis=1, skipna=True)
        # capital investi plancher à 25 % du total de bilan : évite les ROIC absurdes des sociétés à fonds propres quasi nuls
        invested = (df["equity"] + df["debt"] - df["liquidity"]).clip(lower=0.25 * df["assets"].fillna(0.0))
        df["roic"] = (df["ebit"] * (1 - q["tax_rate"]) / invested).where(invested > 0)
        df["fcf_ni"] = (df["fcf"] / df["net_income"]).where(df["net_income"] > 0)
        df["da_known"] = df["da"].notna().astype(float)
        ebitda = df["ebit"] + df["da"].fillna(0.0)
        df["nd_ebitda"] = ((df["debt"] - df["liquidity"]) / ebitda).where(ebitda > 0)
        # solidité jugée sur plusieurs années (moyennes 5 ans) : un exercice de forte dépense d'investissement
        # ou une charge exceptionnelle (acquisition de pharma) ne fait pas « échouer » une société solide à elle seule
        df["roic_avg"] = _mean_years(df["roic"], ay, amy)
        ni_avg, fcf_avg = _mean_years(df["net_income"], ay, amy), _mean_years(df["fcf"], ay, amy)
        df["fcf_ni_avg"] = (fcf_avg / ni_avg).where(ni_avg > 0)
        ebitda_avg = _mean_years(ebitda, q.get("ebitda_avg_years", 3), min(amy, q.get("ebitda_avg_years", 3)))
        df["nd_ebitda_avg"] = ((df["debt"] - df["liquidity"]) / ebitda_avg).where(ebitda_avg > 0)
        fails["rentabilité"] = ~(df["roic_avg"] >= q["roic_min"])
        fails["cash"] = ~(df["fcf_ni_avg"] >= q["fcf_to_net_income_min"])
        fails["dette"] = ~(df["nd_ebitda_avg"] <= q["net_debt_to_ebitda_max"])
        df["quality_ok"] = ~fails.any(axis=1) & df["roic_avg"].notna() & df["fcf_ni_avg"].notna() & df["nd_ebitda_avg"].notna()
    financial = mode == "financial"
    d = r["reverse_dcf"]
    fcf_5y = df["fcf"].shift(5 * TD)
    df["fcf_cagr_5y"] = ((df["fcf"] / fcf_5y) ** 0.2 - 1.0).where((df["fcf"] > 0) & (fcf_5y > 0))
    last = df.iloc[-1]
    df["implied_growth"] = np.nan
    df.loc[df.index[-1], "implied_growth"] = implied_growth(last["ev"], last["fcf"], d["wacc"], d["terminal_growth"], d["years"])
    df["tendu"] = ((df["gap_ma200_pct"] >= r["extension"]["red_min"]) | df["gsy"]).fillna(False)
    df["stale_accounts"] = (df["accounts_age_days"] > 30.44 * r.get("stale_accounts_months", 15)).fillna(True)
    df["color"] = "orange"            # couleur définitive : après la lentille transversale (apply_cross_section)
    df["color_confirmed"] = "orange"
    df["kind"] = "operating"
    last_fails = fails.iloc[-1] if len(fails.columns) else pd.Series(dtype=bool)
    known = {"rentabilité": df["roe_avg" if mode == "financial" else "roic_avg"].iloc[-1], "cash": df["fcf_ni_avg"].iloc[-1], "dette": df["nd_ebitda_avg"].iloc[-1]}
    df.attrs["quality_fails"] = [k for k, v in last_fails.items() if bool(v) and pd.notna(known.get(k))]
    df.attrs["quality_unknown"] = [k for k in last_fails.index if pd.isna(known.get(k))]
    df.attrs["mode"] = mode
    df.attrs["ebit_source"] = ebit_source
    df.attrs["shares_source"] = shares_source
    df.attrs["accounts_as_of"] = accounts_as_of
    df.attrs["shares_ok"] = bool(shares_ok)
    df.attrs["sbc_known"] = bool(sbc_known)
    df.attrs["splits"] = split_list[-4:]
    df.attrs["concepts"] = {k: v.attrs.get("concept") for k, v in f.items() if hasattr(v, "attrs")}
    df.attrs["accounts_currency"] = unit
    df.attrs["price_currency"] = px_ccy
    return df


def analyse_price_only(key: str, spec: dict) -> pd.DataFrame:
    px = yahoo.fetch_close(spec["ticker"])
    df = price_block(px)
    df["V"] = np.nan
    df["color"] = "orange"
    df["color_confirmed"] = "orange"
    df["kind"] = "price_only"
    return df


def analyse_crypto_proxy(key: str, spec: dict) -> pd.DataFrame:
    px = yahoo.fetch_close(spec["ticker"])
    btc = load_signals("btc")
    df = price_block(px)
    b = btc[["color", "color_confirmed", "V"]].reindex(btc.index.union(px.index)).ffill(limit=5).reindex(px.index)
    df["btc_color"] = b["color"]
    df["color"] = b["color"].fillna("orange")
    df["color_confirmed"] = b["color_confirmed"].fillna("orange")
    df["V"] = np.nan
    df["kind"] = "crypto_proxy"
    return df


# ----------------------------------------------------------------------------------------------
def targets() -> list[dict]:
    """Univers Top 100 (data/universe.csv) + compléments de stocks.yaml. Les surcharges de stocks.yaml
    (par symbole) l'emportent : type, nom, cik."""
    from .universe import UNIVERSE_CSV, load

    ex = extras()
    out, seen = [], set()
    if UNIVERSE_CSV.exists():
        u = load()
        for row in u.itertuples():
            if not isinstance(row.symbol, str):
                continue
            flags = {k: (None if pd.isna(getattr(row, k, np.nan)) else bool(getattr(row, k))) for k in ("in_sp500", "in_ndx", "in_world")}
            flags["w_sp500"] = None if pd.isna(getattr(row, "w_sp500", np.nan)) else float(getattr(row, "w_sp500"))
            spec = {"key": row.symbol, "name": row.name, "ticker": row.symbol, "country": row.country, "sector": row.sector, **flags,
                    "industry": row.industry, "weight": float(row.weight), "rank": int(row.rank), "pea": bool(row.pea_eligible_approx),
                    "cik": None if pd.isna(row.cik) else int(row.cik), "type": "operating" if not pd.isna(row.cik) else "price_only",
                    "source": "top100"}
            over = next((v for v in ex.values() if v.get("ticker") == row.symbol), None)
            if over:
                spec.update({k: over[k] for k in ("type", "cik", "name", "extra_ciks") if k in over})
            out.append(spec)
            seen.add(row.symbol)
    for k, v in ex.items():
        if v.get("ticker") in seen:
            continue
        out.append({"key": k, "name": v.get("name", k), "ticker": v["ticker"], "country": v.get("country"), "sector": v.get("sector"),
                    "industry": None, "weight": None, "rank": None, "pea": v.get("pea"), "cik": v.get("cik"),
                    "type": v.get("type", "operating" if v.get("cik") else "price_only"), "source": "stocks.yaml",
                    "extra_ciks": v.get("extra_ciks")})
    return out


def compute_all(limit: int | None = None) -> dict[str, pd.DataFrame]:
    import os

    out = {}
    specs = targets()[:limit] if limit else targets()
    sec_ok = "@" in os.environ.get("SEC_USER_AGENT", "")
    if not sec_ok:
        log.warning("SEC_USER_AGENT absent : toutes les sociétés sont analysées en prix seul (pas de valorisation ni de qualité)")
    n_ok = n_fail = 0
    for spec in specs:
        kind = spec["type"]
        try:
            if kind == "operating" and spec.get("cik") and sec_ok:
                df = analyse_operating(spec["key"], spec)
                if df.attrs.get("accounts_as_of") is None:   # CIK sans comptes XBRL (SK hynix : simple déposant de formulaires) → prix seul
                    df = analyse_price_only(spec["key"], spec)
                    df.attrs["note"] = "CIK sans comptes XBRL : prix seul"
            elif kind == "crypto_proxy":
                df = analyse_crypto_proxy(spec["key"], spec)
            else:
                df = analyse_price_only(spec["key"], spec)
            for k in ("name", "country", "sector", "industry", "weight", "rank", "pea", "source", "ticker", "in_sp500", "in_ndx", "in_world", "w_sp500"):
                df.attrs[k] = spec.get(k)
            out[spec["key"]] = df
            n_ok += 1
        except Exception as exc:  # noqa: BLE001
            log.error("%s (%s) : échec — %s", spec["key"], spec["name"], str(exc)[:160])
            n_fail += 1
        time.sleep(0.6)
    log.info("Actions : %d analysées, %d en échec ; %d avec comptes EDGAR", n_ok, n_fail, sum(1 for d in out.values() if d["kind"].iloc[-1] == "operating"))
    apply_cross_section(out)
    return out


CROSS_METRIC = {"industrial": "ev_ebit", "financial": "pe", "reit": "pe"}


def apply_cross_section(res: dict[str, pd.DataFrame]) -> None:
    """Deuxième lentille (v1.0) : rang du multiple de chaque société parmi les sociétés du même mode (industrielles : EV/EBIT ;
    banques et assureurs : P/E), à chaque date (0 = la moins chère des 100, 100 = la plus chère), puis couleur indicative :
    rouge = chère sous les deux lentilles (≥ 80) ET tendue ; vert = bon marché sous les deux (≤ 30) ET solide ; sinon orange.
    Comptes de plus de 15 mois : orange. Biais de survie : la lentille utilise l'univers d'aujourd'hui (affichage seulement)."""
    r = rules()["stocks"]
    vr = r["valuation"]
    min_n = int(r.get("cross_section_min_members", 5))
    by_mode: dict[str, dict[str, pd.Series]] = {}
    for key, df in res.items():
        if df["kind"].iloc[-1] != "operating":
            continue
        mode = df.attrs.get("mode", "industrial")
        m = df[CROSS_METRIC[mode]].where(df[CROSS_METRIC[mode]] > 0)
        by_mode.setdefault(mode, {})[key] = m[~m.index.duplicated()]
    cross: dict[str, pd.Series] = {}
    for mode, series in by_mode.items():
        if len(series) < min_n:
            continue
        panel = pd.concat(series, axis=1).sort_index().ffill(limit=5)
        valid = panel.notna().sum(axis=1)
        ranks = panel.rank(axis=1, pct=True) * 100.0
        ranks.loc[valid < min_n] = np.nan
        for key in series:
            cross[key] = ranks[key]
    days = int(rules().get("confirmation_days", 5))
    for key, df in res.items():
        if df["kind"].iloc[-1] != "operating":
            continue
        vc = cross.get(key)
        df["V_cross"] = vc.reindex(df.index).ffill(limit=5) if vc is not None else np.nan
        red = (df["V"] >= vr["red_min"]) & (df["V_cross"] >= vr["red_min"]) & df["tendu"]
        green = (df["V"] <= vr["green_max"]) & (df["V_cross"] <= vr["green_max"]) & (df["quality_ok"] == True)   # noqa: E712
        color = pd.Series("orange", index=df.index, dtype=object)
        color[green.fillna(False)] = "green"
        color[red.fillna(False)] = "red"
        color[df["V"].isna() | df["V_cross"].isna() | df["stale_accounts"]] = "orange"
        df["color"] = color
        df["color_confirmed"] = confirmed_color(df["color"], days)
    # écart au secteur (dernière date) : multiple / médiane des sociétés du même secteur et du même mode (≥ 3)
    last = {k: df.iloc[-1] for k, df in res.items() if df["kind"].iloc[-1] == "operating"}
    groups: dict[tuple, list[float]] = {}
    for k, row in last.items():
        mode = res[k].attrs.get("mode", "industrial")
        v = row.get(CROSS_METRIC[mode])
        if v is not None and v == v and v > 0:
            groups.setdefault((res[k].attrs.get("sector"), mode), []).append(float(v))
    for k, row in last.items():
        mode = res[k].attrs.get("mode", "industrial")
        peers = groups.get((res[k].attrs.get("sector"), mode), [])
        v = row.get(CROSS_METRIC[mode])
        res[k].attrs["sector_peers"] = len(peers)
        res[k].attrs["vs_sector"] = (float(v) / float(np.median(peers)) - 1.0) if len(peers) >= 3 and v == v and v and v > 0 else None


def save_all(res: dict[str, pd.DataFrame]) -> None:
    d = SIGNALS_DIR / "stocks"
    d.mkdir(exist_ok=True)
    for old in d.glob("*.parquet"):
        old.unlink()
    latest = {}
    for key, df in res.items():
        safe = key.replace("/", "_")
        df.to_parquet(d / f"{safe}.parquet")
        last = df.iloc[-1]
        rec = {k: (None if isinstance(v, float) and np.isnan(v) else (v.item() if hasattr(v, "item") else v)) for k, v in last.items()}
        rec.update({k: v for k, v in df.attrs.items()})
        rec["date"] = str(df.index[-1].date())
        rec["since"] = _since(df)
        latest[key] = rec
    (DOCS_DIR / "stocks_latest.json").write_text(json.dumps(latest, indent=0, ensure_ascii=False, default=str), encoding="utf-8")


def _since(df: pd.DataFrame) -> str:
    col = df["color_confirmed"]
    last = col.iloc[-1]
    changes = col[col != last]
    start = col.index[0] if changes.empty else col.index[col.index.get_loc(changes.index[-1]) + 1]
    return str(start.date())


def bottom_up_by_index(latest: dict | None = None) -> dict:
    """Valorisation « par le bas » de chaque indice à partir de ses plus grosses sociétés du Top 100 (contexte, sans historique) :
    P/E agrégé (pondéré par les poids MSCI ACWI, moyenne harmonique ≈ Σ capitalisations / Σ bénéfices), et moyennes pondérées
    des deux lentilles. Les sociétés sans comptes ou aux comptes de plus de 15 mois sont exclues."""
    latest = latest if latest is not None else load_latest()
    out = {}
    for key, flag in (("sp500", "in_sp500"), ("ndx", "in_ndx"), ("world", "in_world")):
        mem = [s for s in latest.values() if s.get(flag) and s.get("kind") == "operating" and not s.get("stale_accounts")
               and s.get("mcap") and s.get("net_income") is not None and s.get("weight")]
        if len(mem) < 5:
            continue
        w = np.array([float(s["weight"]) for s in mem])
        ey = np.array([float(s["net_income"]) / float(s["mcap"]) for s in mem])
        pe = float(w.sum() / (w * ey).sum()) if (w * ey).sum() > 0 else None

        def wavg(field):
            v = [(float(s["weight"]), float(s[field])) for s in mem if s.get(field) is not None]
            return None if not v else float(sum(a * b for a, b in v) / sum(a for a, _ in v))
        out[key] = {"n": len(mem), "pe": pe, "v_own": wavg("V"), "v_cross": wavg("V_cross"),
                    "weight_sp500": float(sum(s.get("w_sp500") or 0 for s in mem)) if key == "sp500" else None}
    return out


def load_latest() -> dict:
    p = DOCS_DIR / "stocks_latest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
