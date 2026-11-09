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


def test_split_adjustment_matches_adjusted_prices():
    """Nvidia 10 pour 1 le 10/06/2024 : les nombres d'actions antérieurs sont multipliés par 10 (prix Yahoo ajustés)."""
    from feux.stocks import split_adjust_shares

    sh = pd.DataFrame({"end": pd.to_datetime(["2024-04-28", "2024-07-28"]), "filed": pd.to_datetime(["2024-05-29", "2024-08-28"]),
                       "val": [2.46e9, 2.45e10]})
    adj = split_adjust_shares(sh, [(pd.Timestamp("2021-07-20"), 4.0), (pd.Timestamp("2024-06-10"), 10.0)])
    assert adj["val"].tolist() == [2.46e10, 2.45e10]


def test_split_adjustment_uses_filing_date():
    """Alphabet 20 pour 1 le 18/07/2022 : le 10-Q du 2e trimestre (clos le 30/06) a été déposé le 27/07, APRÈS la division,
    avec des nombres d'actions déjà retraités. Il ne faut pas les multiplier une seconde fois (bogue corrigé : ×20)."""
    from feux.stocks import split_adjust_shares

    sh = pd.DataFrame({"end": pd.to_datetime(["2022-03-31", "2022-06-30"]), "filed": pd.to_datetime(["2022-04-27", "2022-07-27"]),
                       "val": [6.6e8, 1.31e10]})
    adj = split_adjust_shares(sh, [(pd.Timestamp("2022-07-18"), 20.0)])
    assert adj["val"].tolist() == [1.32e10, 1.31e10]


def test_clean_share_counts_scale_errors_and_outliers():
    """McDonald's publie certains trimestres en millions (725,9 au lieu de 725 900 000) ; Wells Fargo, une page de garde à la
    moitié du vrai nombre ; Linde plc, une coquille à 25 000 actions avant la fusion ; zéros (CrowdStrike 2019)."""
    from feux.stocks import clean_share_counts

    ends = pd.date_range("2023-03-31", periods=9, freq="QE")
    sh = pd.DataFrame({"end": ends, "filed": ends + pd.Timedelta(days=35),
                       "val": [25_000.0, 0.0, 722.0e6, 725.9, 722.0, 3.6e8, 714.0e6, 718.2, 710.0e6]})
    out = clean_share_counts(sh)
    assert out["val"].min() > 7e8 and out["val"].max() < 7.3e8           # échelles corrigées, coquille, zéro et demi-valeur écartés
    assert out.attrs["scale_fixed"] == 3 and out.attrs["dropped"] == 3 and out.attrs["spikes"] == 1
    # BHP : deux exercices déclarés pour la seule société australienne (2,95 Md) entre deux exercices consolidés (5,1-5,2 Md)
    ye = pd.date_range("2018-06-30", periods=6, freq="12ME")
    bhp = pd.DataFrame({"end": ye, "filed": ye + pd.Timedelta(days=80), "val": [5.323e9, 5.18e9, 2.946e9, 2.950e9, 5.066e9, 5.066e9]})
    out = clean_share_counts(bhp)
    assert len(out) == 4 and out["val"].min() > 5e9 and out.attrs["spikes"] == 2
    # une baisse durable (rachats) ou une hausse durable (fusion) n'est pas touchée
    sh2 = pd.DataFrame({"end": ends, "filed": ends, "val": [1.0e9, 0.99e9, 0.98e9, 1.5e9, 1.5e9, 1.49e9, 1.48e9, 1.47e9, 1.46e9]})
    assert clean_share_counts(sh2)["val"].tolist() == sh2["val"].tolist()


def test_cross_section_and_indicative_color():
    """Lentille 2 = rang du multiple parmi les sociétés du même mode ; rouge seulement si chère sous les deux lentilles ET tendue."""
    from feux.stocks import apply_cross_section

    idx = pd.date_range("2026-01-01", periods=3)
    res = {}
    for i, ev in enumerate([10, 15, 20, 25, 60]):
        df = pd.DataFrame({"ev_ebit": [float(ev)] * 3, "V": [90.0] * 3, "tendu": [True] * 3, "quality_ok": [True] * 3,
                           "stale_accounts": [False] * 3, "kind": ["operating"] * 3}, index=idx)
        df.attrs.update({"mode": "industrial", "sector": "Tech"})
        res[f"S{i}"] = df
    res["S0"]["V"] = 10.0
    apply_cross_section(res)
    assert res["S4"]["V_cross"].iloc[-1] == 100.0 and res["S4"]["color"].iloc[-1] == "red"     # la plus chère, chère contre son passé, tendue
    assert res["S0"]["V_cross"].iloc[-1] == 20.0 and res["S0"]["color"].iloc[-1] == "green"    # la moins chère, bon marché contre son passé, solide
    assert res["S2"]["color"].iloc[-1] == "orange"                                               # chère contre son passé, médiane contre les autres
    res["S4"]["stale_accounts"] = True
    apply_cross_section(res)
    assert res["S4"]["color"].iloc[-1] == "orange"                                               # comptes trop anciens : jamais coloré
