"""Test de la mesure P/D10 des zones sur la base Jordà-Schularick-Taylor (protocole : research/zones_test_protocol.md).

Usage : python research/zones_test.py chemin/vers/JSTdatasetR6.xlsx
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

GREEN_MAX, CHER_MIN = 40.0, 80.0
rng = np.random.default_rng(20261109)


def pct_window(s: pd.Series, window: int | None, min_obs: int) -> pd.Series:
    """Percentile de la valeur de l'année parmi les `window` dernières années (incluse), ou tout le passé si None."""
    out = pd.Series(np.nan, index=s.index)
    vals = s.to_numpy()
    for i in range(len(vals)):
        if np.isnan(vals[i]):
            continue
        lo = 0 if window is None else max(0, i - window + 1)
        ref = vals[lo:i + 1]
        ref = ref[~np.isnan(ref)]
        if len(ref) < min_obs:
            continue
        out.iloc[i] = 100.0 * (ref <= vals[i]).mean()
    return out


def build(path: str) -> pd.DataFrame:
    d = pd.read_excel(path)
    rows = []
    for c, g in d.groupby("country"):
        g = g.sort_values("year").set_index("year")
        g = g[["eq_tr", "eq_capgain", "eq_dp", "cpi"]].copy()
        if g["eq_tr"].notna().sum() < 40:
            continue
        infl = g["cpi"] / g["cpi"].shift(1)
        real_px = ((1 + g["eq_capgain"]) / infl).cumprod()                 # prix réel (base arbitraire)
        real_tr = ((1 + g["eq_tr"]) / infl)                                 # facteur de rendement total réel de l'année
        real_div = g["eq_dp"] * real_px                                     # dividende réel de l'année, même base
        avg_d = real_div.rolling(10, min_periods=10).mean()
        pd10 = real_px / avg_d
        ma10 = real_px.rolling(10, min_periods=10).mean()
        f = pd.DataFrame({"country": c, "pd10": pd10, "px_ma10": real_px / ma10})
        f["A"] = pct_window(f["pd10"], 20, 5)
        f["B"] = pct_window(f["pd10"], None, 30)
        f["T"] = pct_window(f["px_ma10"], 20, 5)
        for h in (3, 5, 10):
            fwd = real_tr[::-1].rolling(h, min_periods=h).apply(np.prod, raw=True)[::-1].shift(-1)   # années t+1..t+h
            f[f"r{h}"] = fwd ** (1 / h) - 1
        rows.append(f.reset_index())
    return pd.concat(rows, ignore_index=True)


def spearman(x: pd.Series, y: pd.Series) -> float:
    m = x.notna() & y.notna()
    return float(pd.Series(x[m]).rank().corr(pd.Series(y[m]).rank())) if m.sum() > 10 else np.nan


def boot_ci(df: pd.DataFrame, col: str, ycol: str, n: int = 1000) -> tuple[float, float]:
    """Bootstrap par blocs pays × décennies (les rendements à 5 ans se chevauchent dans le temps)."""
    df = df[df[col].notna() & df[ycol].notna()].copy()
    df["blk"] = df["country"] + (df["year"] // 10).astype(str)
    blocks = {k: g for k, g in df.groupby("blk")}
    keys = list(blocks)
    stats = []
    for _ in range(n):
        pick = rng.choice(keys, size=len(keys), replace=True)
        s = pd.concat([blocks[k] for k in pick])
        stats.append(spearman(s[col], s[ycol]))
    return float(np.nanpercentile(stats, 5)), float(np.nanpercentile(stats, 95))


def evaluate(df: pd.DataFrame, col: str) -> dict:
    out = {}
    for h in (3, 5, 10):
        y = f"r{h}"
        m = df[col].notna() & df[y].notna()
        sub = df[m]
        green = sub[col] <= GREEN_MAX
        cher = sub[col] >= CHER_MIN
        rec = {"n": int(m.sum()), "spearman": spearman(sub[col], sub[y]),
               "médiane_verte": float(sub.loc[green, y].median()), "médiane_autres": float(sub.loc[~green, y].median()),
               "médiane_chère": float(sub.loc[cher, y].median()),
               "part_négative_verte": float((sub.loc[green, y] < 0).mean()), "part_négative_chère": float((sub.loc[cher, y] < 0).mean())}
        rec["écart_vert_autres"] = rec["médiane_verte"] - rec["médiane_autres"]
        if h == 5:
            rec["ic90_spearman"] = boot_ci(df, col, y)
            per = {}
            for c, g in sub.groupby("country"):
                gg = g[col] <= GREEN_MAX
                if gg.sum() >= 5 and (~gg).sum() >= 5:
                    per[c] = float(g.loc[gg, y].median() - g.loc[~gg, y].median())
            rec["pays_écart_positif"] = f"{sum(v > 0 for v in per.values())}/{len(per)}"
            rec["par_pays"] = per
        out[f"{h} ans"] = rec
    return out


def main(path: str) -> None:
    df = build(path)
    res = {name: evaluate(df, col) for col, name in (("A", "A_fenêtre_20_ans"), ("B", "B_tout_le_passé"), ("T", "témoin_prix_seul"))}
    # sous-périodes (variante A, 5 ans)
    for lab, (a, b) in {"avant_1950": (1870, 1949), "1950_1989": (1950, 1989), "depuis_1990": (1990, 2020)}.items():
        sub = df[(df["year"] >= a) & (df["year"] <= b)]
        res[f"A_{lab}"] = {k: v for k, v in evaluate(sub, "A")["5 ans"].items() if k not in ("par_pays",)}
    print(json.dumps(res, indent=1, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main(sys.argv[1])
