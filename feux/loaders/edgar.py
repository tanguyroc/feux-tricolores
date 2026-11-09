"""SEC EDGAR — « companyfacts » (XBRL) : comptes trimestriels et annuels avec leur DATE DE DÉPÔT.

C'est la seule source gratuite réellement point-in-time pour les fondamentaux : chaque valeur porte
`filed`, la date à laquelle elle est devenue publique. On reconstitue des séries glissantes sur 12 mois
(TTM) datées du dépôt, et on garde la PREMIÈRE valeur publiée pour chaque période (pas les restatements).

Politique d'accès de la SEC : un User-Agent déclarant un nom et une adresse de contact est exigé
(variable d'environnement SEC_USER_AGENT, ex. « Prenom Nom prenom.nom@example.com »), 10 requêtes/s au plus.
"""
from __future__ import annotations

import json
import os
import re

import pandas as pd

from ..config import RAW_DIR
from . import http_get, log

URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# Concepts par ordre de préférence, en us-gaap (sociétés américaines, 10-K/10-Q) puis ifrs-full (sociétés
# étrangères déposant un 20-F : ASML, Novo Nordisk, TotalEnergies...). flow = sur une période ; instant = à une date.
CONCEPTS = {
    "revenue": ({"us-gaap": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"], "ifrs-full": ["Revenue"]}, "flow"),
    "ebit": ({"us-gaap": ["OperatingIncomeLoss"], "ifrs-full": ["ProfitLossFromOperatingActivities", "ProfitLossBeforeTax"]}, "flow"),
    "net_income": ({"us-gaap": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss",
                            "NetIncomeLossIncludingPortionAttributableToNonredeemableNoncontrollingInterest", "IncomeLossFromContinuingOperations"],
                "ifrs-full": ["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"]}, "flow"),
    "cfo": ({"us-gaap": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
            "ifrs-full": ["CashFlowsFromUsedInOperatingActivities"]}, "flow"),
    "da": ({"us-gaap": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "DepreciationAmortizationAndAccretionNet",
                     "DepreciationAmortizationAndOther"],
            "ifrs-full": ["DepreciationAndAmortisationExpense", "AdjustmentsForDepreciationAndAmortisationExpense",
                          "AdjustmentsForDepreciationAndAmortisationExpenseAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss",
                          "DepreciationAmortisationAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss"]}, "flow"),
    "cash": ({"us-gaap": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
              "ifrs-full": ["CashAndCashEquivalents"]}, "instant"),
    "st_investments": ({"us-gaap": ["ShortTermInvestments", "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"],
                        "ifrs-full": ["OtherCurrentFinancialAssets"]}, "instant"),
    "equity": ({"us-gaap": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
                "ifrs-full": ["EquityAttributableToOwnersOfParent", "Equity"]}, "instant"),
    "assets": ({"us-gaap": ["Assets"], "ifrs-full": ["Assets"]}, "instant"),
    # repli quand le résultat d'exploitation n'est pas publié (pétrole, pharma, banques) : résultat avant impôt + intérêts
    "pretax": ({"us-gaap": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
                            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic"],
                "ifrs-full": ["ProfitLossBeforeTax"]}, "flow"),
    "interest": ({"us-gaap": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"], "ifrs-full": ["InterestExpense", "FinanceCosts"]}, "flow"),
    # v1.0 : rémunération en actions (coût réel, déduite du FCF), retours aux actionnaires, marge brute
    "sbc": ({"us-gaap": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
             "ifrs-full": ["AdjustmentsForSharebasedPayments", "ExpenseFromSharebasedPaymentTransactionsWithEmployees"]}, "flow"),
    "dividends": ({"us-gaap": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
                   "ifrs-full": ["DividendsPaidClassifiedAsFinancingActivities", "DividendsPaidToEquityHoldersOfParentClassifiedAsFinancingActivities", "DividendsPaid"]}, "flow"),
    "buybacks": ({"us-gaap": ["PaymentsForRepurchaseOfCommonStock", "PaymentsForRepurchaseOfEquity"],
                  "ifrs-full": ["PaymentsToAcquireOrRedeemEntitysShares", "PurchaseOfTreasuryShares"]}, "flow"),
    "issuance": ({"us-gaap": ["ProceedsFromIssuanceOfCommonStock", "ProceedsFromStockOptionsExercised", "ProceedsFromIssuanceOfSharesUnderIncentiveAndShareBasedCompensationPlansIncludingStockOptions"],
                  "ifrs-full": ["ProceedsFromIssuingShares", "ProceedsFromExerciseOfOptions"]}, "flow"),
    "gross_profit": ({"us-gaap": ["GrossProfit"], "ifrs-full": ["GrossProfit"]}, "flow"),
    "cost_of_revenue": ({"us-gaap": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"], "ifrs-full": ["CostOfSales"]}, "flow"),
}
# Investissements (capex) : immobilisations corporelles + incorporelles (licences, logiciels : AstraZeneca, Novartis), sommées ;
# un concept combiné, quand il existe pour la période, l'emporte (sinon double compte).
CAPEX_COMBINED = {"us-gaap": ["PaymentsToAcquireProductiveAssets"],
                  "ifrs-full": ["PurchaseOfPropertyPlantAndEquipmentIntangibleAssetsOtherThanGoodwillInvestmentPropertyAndOtherNoncurrentAssets"]}
CAPEX_COMPONENTS = (
    {"us-gaap": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireOtherPropertyPlantAndEquipment", "PaymentsForCapitalImprovements",
                 "PaymentsToAcquireOtherProductiveAssets"],                                   # Verizon : investissements, logiciels compris
     "ifrs-full": ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                   "PurchaseOfOtherLongtermAssetsClassifiedAsInvestingActivities"]},          # Shell : « capital expenditure »
    {"us-gaap": ["PaymentsToAcquireIntangibleAssets"], "ifrs-full": ["PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities"]},
    {"us-gaap": ["PaymentsToDevelopSoftware"]},
)
# Dette financière totale, période par période (v1.0.1) : total publié s'il existe ; sinon dette à long terme TOTALE (part à moins
# d'un an comprise) + emprunts à court terme ; sinon part non courante + part courante (+ court terme). Une dette inconnue reste
# inconnue (jamais zéro) : pas d'EV, test de dette « n.d. ». Concepts relevés dans les comptes des 100 sociétés suivies.
DEBT_TOTAL = {"us-gaap": ["DebtLongtermAndShorttermCombinedAmount", "DebtAndCapitalLeaseObligations"], "ifrs-full": ["Borrowings"]}
DEBT_LT_TOTAL = {"us-gaap": ["LongTermDebt", "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"]}
DEBT_LT_NONCURRENT = {"us-gaap": ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations", "LongTermNotesAndLoans", "LongTermNotesPayable",
                                  "SeniorLongTermNotes", "LongTermLoansPayable", "UnsecuredLongTermDebt", "ConvertibleDebtNoncurrent"],
                      "ifrs-full": ["NoncurrentPortionOfNoncurrentBorrowings", "LongtermBorrowings"]}
DEBT_LT_CURRENT = {"us-gaap": ["LongTermDebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent"],
                   "ifrs-full": ["CurrentPortionOfLongtermBorrowings"]}
DEBT_CURRENT_ALL = {"us-gaap": ["DebtCurrent"], "ifrs-full": ["CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings"]}
DEBT_SHORT = {"us-gaap": ["ShortTermBorrowings", "CommercialPaper", "ShortTermBankLoansAndNotesPayable", "OtherShortTermBorrowings", "NotesPayableCurrent"],
              "ifrs-full": ["ShorttermBorrowings"]}
# Amortissements publiés en deux morceaux (Abbott, Gilead, Merck...) : dépréciation des immobilisations corporelles
# + amortissement des incorporels. Utilisés quand aucun concept « D&A » combiné n'existe ou n'est plus publié.
DA_COMPONENTS = (
    {"us-gaap": ["Depreciation", "DepreciationNonproduction"], "ifrs-full": ["DepreciationPropertyPlantAndEquipment", "DepreciationExpense"]},
    {"us-gaap": ["AmortizationOfIntangibleAssets", "AdjustmentForAmortization"], "ifrs-full": ["AmortisationIntangibleAssetsOtherThanGoodwill", "AmortisationExpense"]},
)
PRETAX_COMPONENTS = (
    {"us-gaap": ["ProfitLoss", "NetIncomeLoss"], "ifrs-full": ["ProfitLoss"]},
    {"us-gaap": ["IncomeTaxExpenseBenefit"], "ifrs-full": ["IncomeTaxExpenseContinuingOperations"]},
)
WEIGHTED_SHARES = {"us-gaap": ["WeightedAverageNumberOfDilutedSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic"],
                   "ifrs-full": ["WeightedAverageShares", "AdjustedWeightedAverageShares"]}
SHARES_CONCEPTS = {"dei": ["EntityCommonStockSharesOutstanding"], "us-gaap": ["CommonStockSharesOutstanding"],
                   "ifrs-full": ["NumberOfSharesOutstanding", "NumberOfSharesIssued"]}
CURRENCY_UNIT = re.compile(r"^[A-Z]{3}$")


def user_agent() -> str:
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in ua:
        raise RuntimeError("SEC_USER_AGENT absent ou sans adresse de contact : la SEC exige « Nom adresse@email ». "
                           "Définir la variable d'environnement (secret GitHub Actions) avant d'utiliser le module actions.")
    return ua


def fetch_companyfacts(cik: int, use_cache: bool = True) -> dict:
    path = RAW_DIR / f"companyfacts_{cik:010d}.json"
    if use_cache and path.exists() and (pd.Timestamp.now() - pd.Timestamp(path.stat().st_mtime, unit="s")).days < 1:
        return json.loads(path.read_text())
    r = http_get(URL.format(cik=cik), headers={"User-Agent": user_agent(), "Accept-Encoding": "gzip, deflate"})
    path.write_bytes(r.content)
    return r.json()


def _facts(cf: dict, taxonomy: str, concept: str) -> pd.DataFrame:
    units = cf.get("facts", {}).get(taxonomy, {}).get(concept, {}).get("units", {})
    rows = []
    for unit, lst in units.items():
        if not (unit == "shares" or CURRENCY_UNIT.match(unit)):
            continue  # on ignore les unités par action (USD/shares) et les ratios
        for f in lst:
            if f.get("form") not in ("10-K", "10-Q", "10-K/A", "10-Q/A", "20-F", "20-F/A", "40-F"):
                continue
            rows.append({"start": f.get("start"), "end": f["end"], "val": f["val"], "filed": f["filed"],
                         "fy": f.get("fy"), "fp": f.get("fp"), "form": f["form"], "unit": unit})
    if not rows:
        return pd.DataFrame(columns=["start", "end", "val", "filed", "fy", "fp", "form", "unit"])
    df = pd.DataFrame(rows)
    # une seule devise : la plus fréquente (certaines sociétés publient des conversions de confort)
    if df["unit"].nunique() > 1:
        df = df[df["unit"] == df["unit"].mode().iloc[0]]
    for c in ("start", "end", "filed"):
        df[c] = pd.to_datetime(df[c])
    return df


def _first_reported(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Pour une même période, garder la première publication (point-in-time, sans restatement)."""
    return df.sort_values("filed").drop_duplicates(keys, keep="first")


def _merge_parts(parts: list[pd.DataFrame]) -> pd.DataFrame:
    """Fusion de plusieurs concepts (dans l'ordre de préférence) : pour chaque fin de période, la valeur PUBLIÉE EN PREMIER
    (point-in-time), à égalité le concept préféré. Tri stable : le résultat ne dépend pas de l'ordre interne de pandas
    (avant la v1.0.1, un tri instable choisissait parfois un concept publié un an plus tard, figeant la série)."""
    tagged = [p.assign(_prio=i) for i, p in enumerate(parts)]
    m = pd.concat(tagged, ignore_index=True)
    m = m.sort_values(["end", "filed", "_prio"], kind="mergesort").drop_duplicates("end", keep="first")
    return m.drop(columns="_prio").reset_index(drop=True)


def _iter_concepts(concepts) -> list[tuple[str, str]]:
    if isinstance(concepts, dict):
        return [(tax, c) for tax, lst in concepts.items() for c in lst]
    return [("us-gaap", c) for c in concepts]


def _quarterize(df: pd.DataFrame) -> pd.DataFrame:
    """Transforme des faits de flux (trimestriels, cumulés depuis le début d'exercice, annuels) en valeurs
    TRIMESTRIELLES datées du dépôt. Première publication conservée. Attribut annual_only si rien de trimestriel."""
    df = df.dropna(subset=["start"]).copy()
    df["days"] = (df["end"] - df["start"]).dt.days
    df = _first_reported(df, ["start", "end"]).sort_values(["start", "end"])
    rows = []
    # 1) trimestres explicites (12 à 17 semaines : 84 à 119 jours ; exercices de 52/53 semaines, PepsiCo, Costco)
    expl = df[(df["days"] >= 80) & (df["days"] <= 120)]
    cc = "concept" in df.columns
    for r in expl.itertuples():
        rows.append({"end": r.end, "filed": r.filed, "val": float(r.val), "kind": "explicit", "concept": r.concept if cc else None})
    # 2) cumuls depuis le même début de période : différences successives (6M−3M, 9M−6M, 12M−9M)
    for _, g in df.groupby("start"):
        g = g.sort_values("end")
        prev = None
        for r in g.itertuples():
            if prev is not None and 80 <= (r.end - prev.end).days <= 120:
                rows.append({"end": r.end, "filed": max(r.filed, prev.filed), "val": float(r.val - prev.val), "kind": "derived",
                             "concept": r.concept if cc else None})
            prev = r
    # 3) annuel − trois trimestres explicites (sociétés sans cumuls)
    q_by_end = {r.end: (float(r.val), r.filed) for r in expl.itertuples()}
    for r in df[(df["days"] >= 350) & (df["days"] <= 380)].itertuples():
        inside = [e for e in q_by_end if r.start < e < r.end]
        if len(inside) == 3 and r.end not in q_by_end:
            rows.append({"end": r.end, "filed": r.filed, "val": float(r.val) - sum(q_by_end[e][0] for e in inside), "kind": "derived",
                         "concept": r.concept if cc else None})
    if not rows:
        a = df[(df["days"] >= 350) & (df["days"] <= 380)]
        if len(a) >= 4:
            out = a[["end", "filed", "val"] + (["concept"] if cc else [])].copy()
            out["val"] = out["val"].astype(float)
            out.attrs["annual_only"] = True
            return out.sort_values("end").reset_index(drop=True)
        return pd.DataFrame(columns=["end", "filed", "val"])
    out = pd.DataFrame(rows)
    out["rank"] = (out["kind"] != "explicit").astype(int)
    out = out.sort_values(["end", "filed", "rank"], kind="mergesort").drop_duplicates("end", keep="first")
    return out[["end", "filed", "val"] + (["concept"] if cc else [])].reset_index(drop=True)


def quarterly_flow(cf: dict, concepts, keep_concept: bool = False) -> pd.DataFrame:
    """Valeurs trimestrielles datées du dépôt. Chaque concept est d'abord mis en trimestres SÉPARÉMENT (une différence de cumuls
    n'associe jamais deux concepts : Union Pacific, Linde, AT&T auraient eu des trimestres faux, v1.0.1), puis les concepts sont
    fusionnés : pour chaque trimestre, la valeur publiée en premier, à égalité le concept listé en premier. Les sociétés changent
    de concept au fil du temps (Revenues → RevenueFromContract...). Déposants de 20-F : valeurs annuelles (attribut annual_only)."""
    parts = []
    for taxonomy, concept in _iter_concepts(concepts):
        df = _facts(cf, taxonomy, concept)
        if df.empty or df["start"].isna().all():
            continue
        q = _quarterize(df)
        if q.empty:
            continue
        annual = bool(q.attrs.get("annual_only"))
        q = q[["end", "filed", "val"]].copy()
        q["concept"] = f"{taxonomy}:{concept}"
        q["unit"] = df["unit"].iloc[0]
        q["annual"] = annual
        parts.append(q)
    if not parts:
        return pd.DataFrame(columns=["end", "filed", "val"])
    quarterly = [q for q in parts if not q["annual"].iloc[0]]
    use = quarterly if quarterly else parts
    unit = pd.concat([q["unit"] for q in use]).mode().iloc[0]
    use = [q for q in use if q["unit"].iloc[0] == unit]
    merged = _merge_parts([q[["end", "filed", "val", "concept"]] for q in use])
    out = merged[["end", "filed", "val"] + (["concept"] if keep_concept else [])].reset_index(drop=True)
    out.attrs["concept"] = " + ".join(dict.fromkeys(merged["concept"]))
    out.attrs["unit"] = unit
    if not quarterly:
        out.attrs["annual_only"] = True
    return out


def summed_flow(cf: dict, groups) -> pd.DataFrame:
    """Somme de plusieurs flux trimestriels (ex. dépréciation + amortissement des incorporels), alignés sur la fin
    de période. Le premier groupe est obligatoire ; les suivants valent 0 quand ils manquent à une date."""
    parts = [quarterly_flow(cf, g) for g in groups]
    base = parts[0]
    if base.empty:
        return base
    out = base.copy()
    concepts = [base.attrs.get("concept", "")]
    for p in parts[1:]:
        if p.empty or p.attrs.get("annual_only") != base.attrs.get("annual_only"):
            continue
        add = p[["end", "filed", "val"]].rename(columns={"filed": "filed_b", "val": "val_b"})
        out = out.merge(add, on="end", how="left")
        out["val"] = out["val"] + out["val_b"].fillna(0.0)
        out["filed"] = out[["filed", "filed_b"]].max(axis=1)
        out = out.drop(columns=["filed_b", "val_b"])
        concepts.append(p.attrs.get("concept", ""))
    out = out.reset_index(drop=True)
    out.attrs.update(base.attrs)
    out.attrs["concept"] = " + ".join(c for c in concepts if c)
    return out


def instant(cf: dict, concepts, taxonomy: str | None = None) -> pd.DataFrame:
    """Valeurs de bilan datées du dépôt. Comme pour les flux, les concepts sont FUSIONNÉS : Qualcomm, Broadcom, Visa ou
    UnitedHealth ont abandonné StockholdersEquity pour la variante « y compris minoritaires » ; prendre le premier concept
    disponible figerait la série à sa dernière publication."""
    pairs = [(taxonomy, c) for c in concepts] if taxonomy else _iter_concepts(concepts)
    parts = []
    for tax, concept in pairs:
        df = _facts(cf, tax, concept)
        if df.empty:
            continue
        out = _first_reported(df, ["end"])[["end", "filed", "val"]].sort_values("end").copy()
        if len(out) >= 4:
            out["concept"] = f"{tax}:{concept}"
            out["unit"] = df["unit"].iloc[0]
            parts.append(out)
    if not parts:
        return pd.DataFrame(columns=["end", "filed", "val"])
    merged = _merge_parts(parts)
    res = merged[["end", "filed", "val"]].reset_index(drop=True)
    res.attrs["concept"] = " + ".join(dict.fromkeys(d["concept"].iloc[0] for d in parts))
    res.attrs["unit"] = parts[0]["unit"].iloc[0]
    return res


def ttm(q: pd.DataFrame) -> pd.DataFrame:
    """Somme glissante des 4 derniers trimestres, datée du dépôt du plus récent (valeurs annuelles : inchangées)."""
    if q.empty or q.attrs.get("annual_only"):
        return q
    q = q.sort_values("end").reset_index(drop=True)
    q["ttm"] = q["val"].rolling(4, min_periods=4).sum()
    # un trimestre manquant ferait additionner quatre trimestres étalés sur plus d'un an : TTM inconnu
    span = (pd.to_datetime(q["end"]) - pd.to_datetime(q["end"]).shift(3)).dt.days
    q.loc[~span.between(250, 300), "ttm"] = float("nan")
    # un TTM n'est connu que lorsque ses 4 trimestres sont déposés
    filed_ns = pd.to_datetime(q["filed"]).astype("datetime64[ns]").astype("int64").astype("float64")
    q["filed_ttm"] = pd.to_datetime(filed_ns.rolling(4, min_periods=4).max())
    out = q.dropna(subset=["ttm"])[["end", "filed_ttm", "ttm"]].rename(columns={"filed_ttm": "filed", "ttm": "val"})
    return out.reset_index(drop=True)


def weighted_shares(cf: dict) -> pd.DataFrame:
    """Nombre moyen d'actions (dilué) par période EXPLICITE (trimestre ≈ 90 j, ou exercice), daté du dépôt.
    Une moyenne ne se dé-cumule pas : on ne garde que les périodes publiées telles quelles."""
    for taxonomy, concept in _iter_concepts(WEIGHTED_SHARES):
        df = _facts(cf, taxonomy, concept)
        if df.empty or df["start"].isna().all():
            continue
        df = df.dropna(subset=["start"]).copy()
        df["days"] = (df["end"] - df["start"]).dt.days
        q = df[(df["days"] >= 80) & (df["days"] <= 100)]
        a = df[(df["days"] >= 350) & (df["days"] <= 380)]
        use = q if len(q) >= 4 else a
        if len(use) >= 4:
            out = _first_reported(use, ["end"])[["end", "filed", "val"]].sort_values("end").reset_index(drop=True)
            out.attrs["concept"] = f"{taxonomy}:{concept} (moyenne pondérée)"
            out.attrs["unit"] = "shares"
            return out
    return pd.DataFrame(columns=["end", "filed", "val"])


def shares_series(cf: dict) -> pd.DataFrame:
    """Nombre d'actions : fusion de toutes les sources (page de garde dei, bilan us-gaap/ifrs, moyennes pondérées),
    la source la plus récente l'emportant pour une même date. Les sociétés changent de concept au fil du temps
    et certaines (Exxon) n'ont la page de garde que depuis peu."""
    parts = []
    for tax, concepts in SHARES_CONCEPTS.items():
        for concept in concepts:
            df = _facts(cf, tax, concept)
            if df.empty:
                continue
            out = _first_reported(df, ["end"])[["end", "filed", "val"]]
            out = out.assign(src=f"{tax}:{concept}")
            parts.append(out)
    ws = weighted_shares(cf)
    if not ws.empty:
        parts.append(ws.assign(src=ws.attrs.get("concept", "moyenne pondérée")))
    if not parts:
        return pd.DataFrame(columns=["end", "filed", "val"])
    use = parts
    merged = _merge_parts(use)
    out = merged[["end", "filed", "val"]].reset_index(drop=True)
    out["val"] = out["val"].astype(float)
    out.attrs["concept"] = " + ".join(dict.fromkeys(d["src"].iloc[0] for d in use))
    out.attrs["unit"] = "shares"
    return out


def implied_shares(net_income_ttm: pd.DataFrame, cf: dict) -> pd.DataFrame:
    """Dernier recours (Visa, Berkshire : actions multi-classes) : actions implicites = résultat net / BPA dilué,
    tous deux sur 12 mois glissants."""
    eps_q = quarterly_flow(cf, {"us-gaap": ["EarningsPerShareDiluted", "EarningsPerShareBasic"], "ifrs-full": ["DilutedEarningsLossPerShare", "BasicEarningsLossPerShare"]})
    if eps_q.empty or net_income_ttm is None or net_income_ttm.empty:
        return pd.DataFrame(columns=["end", "filed", "val"])
    eps_ttm = ttm(eps_q)
    m = net_income_ttm.merge(eps_ttm, on="end", suffixes=("_ni", "_eps"))
    m = m[m["val_eps"].abs() > 1e-9]
    if m.empty:
        return pd.DataFrame(columns=["end", "filed", "val"])
    out = pd.DataFrame({"end": m["end"], "filed": m[["filed_ni", "filed_eps"]].max(axis=1), "val": (m["val_ni"] / m["val_eps"]).astype(float)})
    out = out.sort_values("end").reset_index(drop=True)
    out.attrs["concept"] = "résultat net / BPA dilué (actions implicites)"
    out.attrs["unit"] = "shares"
    return out


def capex_series(cf: dict) -> pd.DataFrame:
    """Investissements sur 12 mois glissants. Base : immobilisations corporelles (ou, selon les périodes, le concept combiné
    corporels + incorporels). Les incorporels (licences, fréquences, logiciels) s'ajoutent aux trimestres dont la base ne
    les comprend pas déjà (pas de double compte)."""
    ppe, comb = CAPEX_COMPONENTS[0], CAPEX_COMBINED
    base_concepts = {t: ppe.get(t, []) + comb.get(t, []) for t in ("us-gaap", "ifrs-full")}
    base = quarterly_flow(cf, base_concepts, keep_concept=True)
    if base.empty:
        return pd.DataFrame(columns=["end", "filed", "val"])
    combined = {f"{t}:{c}" for t, lst in comb.items() for c in lst}
    out = base.copy()
    used = [base.attrs.get("concept", "")]
    for g in CAPEX_COMPONENTS[1:]:
        p = quarterly_flow(cf, g)
        if p.empty or bool(p.attrs.get("annual_only")) != bool(base.attrs.get("annual_only")):
            continue
        add = p[["end", "filed", "val"]].rename(columns={"filed": "filed_b", "val": "val_b"})
        out = out.merge(add, on="end", how="left")
        take = ~out["concept"].isin(combined) & out["val_b"].notna()
        out.loc[take, "val"] = out.loc[take, "val"] + out.loc[take, "val_b"]
        out.loc[take, "filed"] = out.loc[take, ["filed", "filed_b"]].max(axis=1)
        out = out.drop(columns=["filed_b", "val_b"])
        used.append(p.attrs.get("concept", ""))
    q = out[["end", "filed", "val"]].reset_index(drop=True)
    q.attrs.update(base.attrs)
    q.attrs["concept"] = " + ".join(c for c in used if c)
    t = ttm(q)
    t.attrs.update(q.attrs)
    return t


def _instant_by_end(cf: dict, concepts) -> dict:
    """{fin de période: (valeur, date de dépôt, concept)} : pour chaque date, la valeur publiée en premier, à égalité le concept
    listé en premier (v1.0.1 : l'ordre de la liste seul faisait parfois attendre un dépôt plus tardif)."""
    out = {}
    for tax, concept in _iter_concepts(concepts):
        df = _facts(cf, tax, concept)
        if df.empty:
            continue
        for r in _first_reported(df, ["end"]).itertuples():
            cur = out.get(r.end)
            if cur is None or r.filed < cur[1]:
                out[r.end] = (float(r.val), r.filed, f"{tax}:{concept}")
    return out


def interest_evidence(cf: dict) -> pd.DataFrame:
    """Charges d'intérêts publiées, ramenées à l'année (toute période), datées du dépôt : preuve d'endettement, même quand les
    trimestres ne permettent pas de somme sur 12 mois (Berkshire)."""
    rows = []
    for tax, concept in _iter_concepts(CONCEPTS["interest"][0]):
        df = _facts(cf, tax, concept)
        if df.empty or df["start"].isna().all():
            continue
        df = df.dropna(subset=["start"])
        days = (df["end"] - df["start"]).dt.days.clip(lower=1)
        ok = days >= 80
        rows.append(pd.DataFrame({"end": df["end"][ok], "filed": df["filed"][ok], "val": (df["val"][ok].abs() * 365.0 / days[ok]).astype(float)}))
    if not rows:
        return pd.DataFrame(columns=["end", "filed", "val"])
    return pd.concat(rows).sort_values("filed").reset_index(drop=True)


def debt_series(cf: dict) -> pd.DataFrame:
    """Dette financière totale par date de bilan, datée du dépôt le plus tardif des composantes utilisées."""
    tot, ltt, nc, cur, call, sht = (_instant_by_end(cf, c) for c in (DEBT_TOTAL, DEBT_LT_TOTAL, DEBT_LT_NONCURRENT,
                                                                       DEBT_LT_CURRENT, DEBT_CURRENT_ALL, DEBT_SHORT))
    rows, used = [], {}
    for end in sorted(set(tot) | set(ltt) | set(nc)):
        cands = []                                             # (rang de qualité, composantes)
        if end in tot:
            cands.append((0, [tot[end]]))
        if end in ltt:
            cands.append((1, [ltt[end]] + ([sht[end]] if end in sht else [])))
        if end in nc and end in call:
            cands.append((2, [nc[end], call[end]]))            # part courante totale = part à moins d'un an + court terme
        if end in nc:
            cands.append((3, [x[end] for x in (nc, cur, sht) if end in x]))
        if not cands:
            continue
        # la construction disponible LA PREMIÈRE (date de dépôt de sa dernière composante), à égalité la plus complète
        # (v1.0.1 : PepsiCo, dette de fin 2022 connue en février au lieu d'avril)
        _, comps = min(cands, key=lambda c: (max(x[1] for x in c[1]), c[0]))
        rows.append({"end": end, "filed": max(c[1] for c in comps), "val": sum(c[0] for c in comps)})
        for c in comps:
            used[c[2]] = True
    if not rows:
        return pd.DataFrame(columns=["end", "filed", "val"])
    out = pd.DataFrame(rows).sort_values("end").reset_index(drop=True)
    out.attrs["concept"] = " + ".join(used)
    units = [_facts(cf, *c.split(":", 1))["unit"] for c in list(used)[:1]]
    out.attrs["unit"] = units[0].iloc[0] if units and len(units[0]) else None
    return out


def merge_companyfacts(cfs: list[dict]) -> dict:
    """Concatène les faits de plusieurs CIK (réorganisation en holding : l'historique reste sur l'ancien CIK)."""
    out = {"facts": {}}
    for cf in cfs:
        for taxo, tags in cf.get("facts", {}).items():
            dst = out["facts"].setdefault(taxo, {})
            for tag, body in tags.items():
                d = dst.setdefault(tag, {"units": {}})
                for unit, arr in body.get("units", {}).items():
                    d["units"].setdefault(unit, []).extend(arr)
    return out


def public_float(cf: dict) -> pd.DataFrame:
    """Flottant en dollars déclaré en couverture du 10-K (dei:EntityPublicFloat), daté du dépôt."""
    df = _facts(cf, "dei", "EntityPublicFloat")
    if df.empty:
        return pd.DataFrame(columns=["end", "filed", "val"])
    out = _first_reported(df, ["end"])[["end", "filed", "val"]].sort_values("end").reset_index(drop=True)
    out.attrs["concept"] = "dei:EntityPublicFloat"
    out.attrs["unit"] = df["unit"].iloc[0]
    return out


def fundamentals(cik: int, extra_ciks: tuple[int, ...] = ()) -> dict[str, pd.DataFrame]:
    """Toutes les séries (TTM pour les flux, dernière valeur pour les stocks), chacune avec end/filed/val."""
    cf = fetch_companyfacts(cik)
    if extra_ciks:
        cf = merge_companyfacts([cf] + [fetch_companyfacts(int(c)) for c in extra_ciks])
    out = {}
    for key, (concepts, kind) in CONCEPTS.items():
        if kind == "flow":
            q = quarterly_flow(cf, concepts)
            ref_end = out["net_income"]["end"].max() if "net_income" in out and not out["net_income"].empty else None
            stale = q.empty or (ref_end is not None and q["end"].max() < ref_end - pd.Timedelta(days=400))
            if key == "da" and stale:
                # concept combiné absent, ou abandonné depuis plus d'un an : dépréciation + amortissement des incorporels
                parts = summed_flow(cf, DA_COMPONENTS)
                if not parts.empty and (q.empty or parts["end"].max() > q["end"].max()):
                    q = parts
            if key == "pretax" and stale:
                # ni résultat d'exploitation ni résultat avant impôt publiés : résultat net + impôt sur les bénéfices
                parts = summed_flow(cf, PRETAX_COMPONENTS)
                if not parts.empty and len(parts) >= 2 and (q.empty or parts["end"].max() > q["end"].max()):
                    q = parts
            t = ttm(q)
            t.attrs.update(q.attrs)
            out[key] = t
        else:
            out[key] = instant(cf, concepts)
    out["capex"] = capex_series(cf)
    out["debt"] = debt_series(cf)
    out["interest_evidence"] = interest_evidence(cf)
    out["shares"] = shares_series(cf)
    stale = out["shares"].empty or out["shares"]["end"].max() < pd.Timestamp.now() - pd.DateOffset(years=2)
    if stale:
        implied = implied_shares(out["net_income"], cf)
        if not implied.empty and (out["shares"].empty or implied["end"].max() > out["shares"]["end"].max()):
            out["shares"] = implied
    out["public_float"] = public_float(cf)
    out["shares_stale"] = out["shares"].empty or out["shares"]["end"].max() < pd.Timestamp.now() - pd.DateOffset(years=2)
    units = {v.attrs.get("unit") for k, v in out.items()
             if hasattr(v, "attrs") and k != "public_float" and v.attrs.get("unit") and v.attrs.get("unit") != "shares"}
    if len(units) > 1:
        log.warning("CIK %d : plusieurs devises dans les comptes (%s) ; vérifier la cohérence avec la devise du cours", cik, units)
    log.info("EDGAR CIK %d : %s%s", cik, ", ".join(f"{k}={len(v)}" for k, v in out.items() if hasattr(v, "attrs")),
             " (annuel seulement : déposant 20-F)" if any(hasattr(v, "attrs") and v.attrs.get("annual_only") for v in out.values()) else "")
    return out
