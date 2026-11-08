"""Tests du module actions : reconstruction TTM point-in-time depuis un companyfacts synthétique, DCF inversé."""
import numpy as np
import pandas as pd

from feux.loaders import edgar
from feux.stocks import implied_growth


def _fact(start, end, val, filed, form, fy, fp):
    return {"start": start, "end": end, "val": val, "accn": "x", "fy": fy, "fp": fp, "form": form, "filed": filed}


def _companyfacts():
    # exercice calendaire 2023 : T1..T3 en 10-Q, annuel en 10-K (T4 = annuel − T1 − T2 − T3), puis 2024 idem
    facts = []
    q = {2023: [10, 11, 12], 2024: [13, 14, 15]}
    annual = {2023: 50, 2024: 60}            # T4 = 17 en 2023, 18 en 2024
    for fy, vals in q.items():
        for i, v in enumerate(vals):
            start = f"{fy}-{3 * i + 1:02d}-01"
            end = pd.Timestamp(f"{fy}-{3 * i + 3:02d}-01") + pd.offsets.MonthEnd(0)
            filed = end + pd.Timedelta(days=40)
            facts.append(_fact(start, str(end.date()), v, str(filed.date()), "10-Q", fy, f"Q{i + 1}"))
        facts.append(_fact(f"{fy}-01-01", f"{fy}-12-31", annual[fy], f"{fy + 1}-02-15", "10-K", fy, "FY"))
        # restatement ultérieur du T1 : doit être ignoré (première publication conservée)
        facts.append(_fact(f"{fy}-01-01", f"{fy}-03-31", 999, f"{fy + 1}-03-01", "10-K/A", fy, "Q1"))
    return {"facts": {"us-gaap": {"OperatingIncomeLoss": {"units": {"USD": facts}}}}}


def test_quarterly_flow_derives_q4_and_keeps_first_report():
    q = edgar.quarterly_flow(_companyfacts(), ["OperatingIncomeLoss"])
    vals = dict(zip(q["end"].dt.strftime("%Y-%m-%d"), q["val"]))
    assert vals["2023-03-31"] == 10            # pas 999
    assert vals["2023-12-31"] == 17            # 50 − 33
    assert vals["2024-12-31"] == 18
    q4 = q[q["end"] == "2023-12-31"].iloc[0]
    assert str(q4["filed"].date()) == "2024-02-15"   # daté du dépôt du 10-K


def test_ttm_is_dated_by_latest_filing():
    t = edgar.ttm(edgar.quarterly_flow(_companyfacts(), ["OperatingIncomeLoss"]))
    row = t[t["end"] == "2024-03-31"].iloc[0]
    assert row["val"] == 11 + 12 + 17 + 13
    assert str(row["filed"].date()) == "2024-05-10"   # dépôt du T1 2024 (31/03 + 40 j)


def test_implied_growth_round_trip():
    # si le FCF croît de 8 %/an pendant 10 ans puis 2,5 %, à 9 % de WACC, la VAN égale l'EV par construction
    fcf, g, wacc, gt, n = 100.0, 0.08, 0.09, 0.025, 10
    flows = fcf * (1 + g) ** np.arange(1, n + 1)
    disc = (1 + wacc) ** np.arange(1, n + 1)
    ev = (flows / disc).sum() + flows[-1] * (1 + gt) / (wacc - gt) / disc[-1]
    assert abs(implied_growth(ev, fcf, wacc, gt, n) - g) < 1e-6
    assert np.isnan(implied_growth(1000.0, -5.0, wacc, gt, n))


def test_annual_only_fallback_for_20f_filers():
    facts = []
    for fy, v in [(2020, 10), (2021, 12), (2022, 15), (2023, 18), (2024, 20)]:
        facts.append(_fact(f"{fy}-01-01", f"{fy}-12-31", v, f"{fy + 1}-03-01", "20-F", fy, "FY"))
    cf = {"facts": {"ifrs-full": {"ProfitLossFromOperatingActivities": {"units": {"EUR": facts}}}}}
    q = edgar.quarterly_flow(cf, {"us-gaap": ["OperatingIncomeLoss"], "ifrs-full": ["ProfitLossFromOperatingActivities"]})
    assert q.attrs.get("annual_only") is True and q.attrs["unit"] == "EUR" and len(q) == 5
    t = edgar.ttm(q)
    assert list(t["val"]) == [10, 12, 15, 18, 20]      # inchangé : une année = déjà 12 mois


def _instant_facts(vals_by_end, filed_lag=40):
    out = []
    for end, v in vals_by_end.items():
        e = pd.Timestamp(end)
        out.append({"start": None, "end": str(e.date()), "val": v, "accn": "x", "fy": e.year, "fp": "FY", "form": "10-Q",
                    "filed": str((e + pd.Timedelta(days=filed_lag)).date())})
    return out


def test_instant_merges_concepts_most_recent_first():
    # StockholdersEquity abandonné fin 2019, remplacé par la variante « y compris minoritaires » (Qualcomm, Visa, Broadcom…)
    old = _instant_facts({f"{y}-12-31": 100 + y - 2015 for y in range(2015, 2020)})
    new = _instant_facts({f"{y}-12-31": 200 + y - 2018 for y in range(2018, 2026)})
    cf = {"facts": {"us-gaap": {"StockholdersEquity": {"units": {"USD": old}},
                                "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": {"units": {"USD": new}}}}}
    s = edgar.instant(cf, edgar.CONCEPTS["equity"][0])
    assert str(s["end"].max().date()) == "2025-12-31"                    # la série ne s'arrête plus en 2019
    assert s.loc[s["end"] == pd.Timestamp("2019-12-31"), "val"].item() == 201   # à date commune, le concept le plus récent l'emporte
    assert s.loc[s["end"] == pd.Timestamp("2015-12-31"), "val"].item() == 100   # l'ancien concept comble le passé


def test_summed_flow_adds_depreciation_and_amortization():
    cf = _companyfacts()
    dep = cf["facts"]["us-gaap"]["OperatingIncomeLoss"]["units"]["USD"]
    amort = [dict(f, val=4 if f["fp"] == "FY" else 1) for f in dep]   # 1 par trimestre, 4 sur l'exercice
    cf2 = {"facts": {"us-gaap": {"Depreciation": {"units": {"USD": dep}}, "AmortizationOfIntangibleAssets": {"units": {"USD": amort}}}}}
    q_dep = edgar.quarterly_flow(cf2, {"us-gaap": ["Depreciation"]})
    q_sum = edgar.summed_flow(cf2, edgar.DA_COMPONENTS)
    assert len(q_sum) == len(q_dep)
    assert (q_sum["val"].to_numpy() - q_dep["val"].to_numpy() == 1).all()
    assert "Depreciation" in q_sum.attrs["concept"] and "Amortization" in q_sum.attrs["concept"]


def test_asof_forgets_stale_values():
    from feux.stocks import _asof

    cal = pd.bdate_range("2015-01-01", "2026-11-06")
    df = pd.DataFrame({"end": pd.to_datetime(["2015-03-31", "2015-06-30"]), "filed": pd.to_datetime(["2015-05-01", "2015-08-01"]), "val": [1.0, 2.0]})
    s = _asof(df, cal)
    assert s.loc["2015-09-01"] == 2.0                      # disponible après publication
    assert s.loc["2016-01-04"] == 2.0                      # 6 mois plus tard : encore valable
    assert np.isnan(s.iloc[-1])                            # dix ans plus tard : oubliée (KLA, résultat d'exploitation non publié depuis 2015)
