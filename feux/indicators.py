"""Indicateurs déterministes. Aucune donnée future : toutes les fenêtres sont rétrospectives."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252
CAL_DAYS_PER_YEAR = 365


def rolling_pct(s: pd.Series, window: int, min_periods: int) -> pd.Series:
    """Percentile (0-100) de la dernière valeur dans sa fenêtre glissante (fenêtre incluse)."""
    return 100.0 * s.rolling(window, min_periods=min_periods).rank(pct=True)


def expanding_pct(s: pd.Series, min_periods: int) -> pd.Series:
    return 100.0 * s.expanding(min_periods=min_periods).rank(pct=True)


def rolling_z(s: pd.Series, window: int, min_periods: int) -> pd.Series:
    r = s.rolling(window, min_periods=min_periods)
    return (s - r.mean()) / r.std(ddof=0)


def pct_against_reference(values: pd.Series, reference: pd.Series, window: int, min_periods: int) -> pd.Series:
    """Percentile de `values[t]` par rapport aux `window` dernières observations de `reference`
    disponibles à la date t (reference indexée par date, triée). Utilisé pour comparer une valeur
    « vivante » quotidienne (CAPE ajusté du prix du jour) à l'historique mensuel."""
    ref_idx = reference.index
    ref_vals = reference.to_numpy()
    out = np.full(len(values), np.nan)
    pos = ref_idx.searchsorted(values.index, side="right")  # nb de points de référence <= t
    for i, (v, n) in enumerate(zip(values.to_numpy(), pos)):
        if n < min_periods or np.isnan(v):
            continue
        ref = ref_vals[max(0, n - window):n]
        ref = ref[~np.isnan(ref)]
        if len(ref) < min_periods:
            continue
        out[i] = 100.0 * ((ref < v).sum() + 0.5 * (ref == v).sum() + 0.5) / (len(ref) + 1)
    return pd.Series(out, index=values.index)


def drawdown(px: pd.Series) -> pd.Series:
    """Baisse depuis le plus haut historique, en fraction positive (0.25 = -25 %)."""
    return 1.0 - px / px.cummax()


def gap_to_ma(px: pd.Series, window: int) -> pd.Series:
    return px / px.rolling(window, min_periods=window).mean() - 1.0


def momentum(px: pd.Series, periods: int) -> pd.Series:
    return px / px.shift(periods) - 1.0


def gsy_flag(px: pd.Series, runup_periods: int, short_periods: int, runup_min: float) -> pd.Series:
    """Greenwood-Shleifer-You : hausse >= runup_min sur `runup_periods` ET accélération
    (pente annualisée récente > pente annualisée de toute la hausse)."""
    runup = px / px.shift(runup_periods) - 1.0
    years_long = runup_periods / short_periods  # en unités de « période courte »
    ann_long = (px / px.shift(runup_periods)) ** (1.0 / years_long) - 1.0
    ann_short = px / px.shift(short_periods) - 1.0
    flag = (runup >= runup_min) & (ann_short > ann_long)
    return flag.fillna(False).astype(bool)


def monthly_closes(px: pd.Series) -> pd.Series:
    return px.resample("ME").last().dropna()


def sma_month_flag(px: pd.Series, months: int) -> pd.Series:
    """Drapeau « tendance cassée » : clôture mensuelle < moyenne mobile `months` mois.
    Indexé par fin de mois ; connu en fin de mois, à appliquer le mois suivant."""
    m = monthly_closes(px)
    sma = m.rolling(months, min_periods=months).mean()
    return (m < sma).where(sma.notna())


def cape_pit(P: pd.Series, E: pd.Series, CPI: pd.Series, lag_months: int, years: int = 10) -> pd.Series:
    """CAPE point-in-time : bénéfices décalés de `lag_months`, moyenne 10 ans en dollars du mois courant.
    Toutes les séries sont mensuelles (fin de mois) et alignées."""
    realE = (E / CPI).shift(lag_months)            # bénéfices réels disponibles à la date m
    avg = realE.rolling(12 * years, min_periods=12 * years).mean()
    return P / (CPI * avg)


def excess_cape_yield(cape: pd.Series, GS10: pd.Series, CPI: pd.Series, years: int = 10) -> pd.Series:
    infl = (CPI / CPI.shift(12 * years)) ** (1.0 / years) - 1.0
    real_rate = GS10 / 100.0 - infl
    return 1.0 / cape - real_rate
