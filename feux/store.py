"""Stockage point-in-time.

Chaque série est un DataFrame à trois colonnes :
  ref_date        date à laquelle la valeur se rapporte (fin de mois, jour de bourse...)
  available_date  première date à laquelle la valeur était connue
  value           valeur numérique

Règle : un calcul daté du jour J n'utilise que les lignes dont available_date <= J.
"""
from __future__ import annotations

import pandas as pd

from .config import SERIES_DIR

COLUMNS = ["ref_date", "available_date", "value"]


def make_series(ref_dates, values, available_dates=None, lag: pd.DateOffset | pd.Timedelta | None = None,
                dropna: bool = True) -> pd.DataFrame:
    """`dropna=False` pour les indicateurs dérivés : un NaN doit rester « inconnu » et ne pas laisser
    la dernière valeur connue se propager par merge_asof."""
    ref = pd.to_datetime(pd.Index(ref_dates))
    if available_dates is None:
        avail = ref + lag if lag is not None else ref
    else:
        avail = pd.to_datetime(pd.Index(available_dates))
    vals = pd.to_numeric(pd.Series(getattr(values, "to_numpy", lambda: values)()), errors="coerce").to_numpy()
    df = pd.DataFrame({"ref_date": pd.DatetimeIndex(ref).astype("datetime64[ns]"),
                       "available_date": pd.DatetimeIndex(avail).astype("datetime64[ns]"), "value": vals})
    if dropna:
        df = df.dropna(subset=["value"])
    df = df.sort_values("ref_date").drop_duplicates("ref_date", keep="last")
    return df.reset_index(drop=True)


def save(name: str, df: pd.DataFrame) -> None:
    df = df[COLUMNS].copy()
    df.to_parquet(SERIES_DIR / f"{name}.parquet", index=False)


def load(name: str) -> pd.DataFrame:
    path = SERIES_DIR / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Série absente : {name} ({path}). Lancer `python -m feux update`.")
    df = pd.read_parquet(path)
    return _normalize(df)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in ("ref_date", "available_date"):
        df[c] = pd.to_datetime(df[c]).astype("datetime64[ns]")
    return df


def exists(name: str) -> bool:
    return (SERIES_DIR / f"{name}.parquet").exists()


def as_of(df: pd.DataFrame, calendar: pd.DatetimeIndex, value_col: str = "value") -> pd.Series:
    """Pour chaque date du calendrier, dernière valeur DISPONIBLE (available_date <= date).

    C'est le cœur de la discipline point-in-time : on ne regarde jamais une valeur
    avant sa date de publication, même si sa date de référence est antérieure.
    """
    d = _normalize(df).sort_values("available_date")[["available_date", value_col]]
    cal = pd.DataFrame({"available_date": pd.DatetimeIndex(calendar).astype("datetime64[ns]")})
    merged = pd.merge_asof(cal, d, on="available_date", direction="backward")
    return pd.Series(merged[value_col].to_numpy(), index=calendar, name=value_col)


def to_indexed(df: pd.DataFrame) -> pd.Series:
    """Série indexée par ref_date (usage : calculs sur la série elle-même)."""
    return pd.Series(df["value"].to_numpy(), index=pd.DatetimeIndex(df["ref_date"]), name="value").sort_index()
