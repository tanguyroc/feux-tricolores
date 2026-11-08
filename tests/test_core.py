"""Tests unitaires : discipline point-in-time, indicateurs, règles de couleur, garde-fou des explications."""
import numpy as np
import pandas as pd
import pytest

from feux import indicators as ind
from feux import store
from feux.explain import check_numbers
from feux.signals import _colorize_index


def test_as_of_never_reads_before_availability():
    df = store.make_series(["2020-01-31", "2020-02-29"], [1.0, 2.0], lag=pd.Timedelta(days=25))
    cal = pd.DatetimeIndex(["2020-02-01", "2020-02-24", "2020-02-25", "2020-03-20", "2020-03-26"])
    got = store.as_of(df, cal)
    assert np.isnan(got.iloc[0])            # janvier pas encore publié le 1er février
    assert np.isnan(got.iloc[1])            # ni le 24
    assert got.iloc[2] == 1.0               # publié le 25
    assert got.iloc[3] == 1.0               # février pas encore publié le 20 mars
    assert got.iloc[4] == 2.0


def test_make_series_keeps_nan_when_asked():
    df = store.make_series(["2020-01-31", "2020-02-29"], [1.0, np.nan], dropna=False)
    assert len(df) == 2
    cal = pd.DatetimeIndex(["2020-03-05"])
    assert np.isnan(store.as_of(df, cal).iloc[0])   # le NaN de février ne laisse pas janvier se propager


def test_rolling_pct_is_rank_of_last_value():
    s = pd.Series(np.arange(1, 11, dtype=float))
    p = ind.rolling_pct(s, 5, 5)
    assert p.iloc[-1] == 100.0              # la plus haute de sa fenêtre
    s2 = pd.Series([5, 4, 3, 2, 1], dtype=float)
    assert ind.rolling_pct(s2, 5, 5).iloc[-1] == 20.0


def test_gsy_flag_requires_runup_and_acceleration():
    idx = pd.date_range("2000-01-01", periods=600, freq="B")
    slow = pd.Series(np.linspace(100, 210, 600), index=idx)          # +110 % linéaire : pas d'accélération
    fast = pd.Series(100 * np.exp(np.linspace(0, 1.0, 600) ** 2), index=idx)   # convexe : +165 %/2 ans et accélère
    assert not ind.gsy_flag(slow, 504, 126, 1.0).iloc[-1]
    assert ind.gsy_flag(fast, 504, 126, 1.0).iloc[-1]


def test_cape_pit_matches_hand_computation():
    idx = pd.date_range("2000-01-31", periods=130, freq="ME")
    P = pd.Series(100.0, index=idx)
    E = pd.Series(5.0, index=idx)
    CPI = pd.Series(100.0, index=idx)
    cape = ind.cape_pit(P, E, CPI, lag_months=3)
    assert np.isnan(cape.iloc[121])          # 120 mois + 3 de décalage nécessaires
    assert abs(cape.iloc[-1] - 20.0) < 1e-9  # 100 / 5


def _frame(**kw):
    base = dict(V=50.0, X=50.0, E=50.0, P=50.0, drawdown=0.0, gsy=False, falling_knife_cond=False)
    base.update(kw)
    return pd.DataFrame({k: [v] for k, v in base.items()}, index=pd.DatetimeIndex(["2024-01-02"]))


def test_colors_and_precedence():
    assert _colorize_index(_frame())["color"].iloc[0] == "orange"
    assert _colorize_index(_frame(V=85, X=95))["color"].iloc[0] == "red"
    assert _colorize_index(_frame(V=85, E=85))["color"].iloc[0] == "red"
    assert _colorize_index(_frame(V=85, gsy=True))["color"].iloc[0] == "red"
    assert _colorize_index(_frame(V=85))["color"].iloc[0] == "orange"        # cher mais ni tendu ni euphorique
    assert _colorize_index(_frame(V=30))["color"].iloc[0] == "green"
    assert _colorize_index(_frame(V=60, drawdown=0.3, P=90))["color"].iloc[0] == "green"   # capitulation
    assert _colorize_index(_frame(V=85, E=85, drawdown=0.3, P=90))["color"].iloc[0] == "green"  # capitulation > rouge
    assert _colorize_index(_frame(V=np.nan, X=95))["color"].iloc[0] == "orange"           # V inconnu : jamais rouge


def test_check_numbers_flags_invented_values():
    row = pd.Series({"V": 97.6, "cape_live": 39.3, "drawdown": 0.057})
    assert check_numbers("V = 98 (CAPE 39,3), baisse 5,7 %", row) == []
    assert check_numbers("V = 98, CAPE 42,0", row) == ["42,0"]
