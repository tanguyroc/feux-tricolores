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
    "ebit": ({"us-gaap": ["OperatingIncomeLoss"], "ifrs-full": ["ProfitLossFromOperatingActivities"]}, "flow"),
    "net_income": ({"us-gaap": ["NetIncomeLoss"], "ifrs-full": ["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"]}, "flow"),
    "cfo": ({"us-gaap": ["NetCashProvidedByUsedInOperatingActivities"], "ifrs-full": ["CashFlowsFromUsedInOperatingActivities"]}, "flow"),
    "capex": ({"us-gaap": ["PaymentsToAcquirePropertyPlantAndEquipment"], "ifrs-full": ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"]}, "flow"),
    "da": ({"us-gaap": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "DepreciationAmortizationAndAccretionNet"],
            "ifrs-full": ["DepreciationAndAmortisationExpense"]}, "flow"),
    "cash": ({"us-gaap": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
              "ifrs-full": ["CashAndCashEquivalents"]}, "instant"),
    "st_investments": ({"us-gaap": ["ShortTermInvestments", "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"],
                        "ifrs-full": ["OtherCurrentFinancialAssets"]}, "instant"),
    "debt_lt": ({"us-gaap": ["LongTermDebtNoncurrent", "LongTermDebt"], "ifrs-full": ["LongtermBorrowings", "NoncurrentPortionOfNoncurrentBorrowings"]}, "instant"),
    "debt_st": ({"us-gaap": ["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"], "ifrs-full": ["ShorttermBorrowings", "CurrentPortionOfLongtermBorrowings"]}, "instant"),
    "equity": ({"us-gaap": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
                "ifrs-full": ["EquityAttributableToOwnersOfParent", "Equity"]}, "instant"),
}
SHARES_CONCEPTS = ["EntityCommonStockSharesOutstanding"]  # taxonomie dei (10-K, 10-Q et 20-F)
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


def _iter_concepts(concepts) -> list[tuple[str, str]]:
    if isinstance(concepts, dict):
        return [(tax, c) for tax, lst in concepts.items() for c in lst]
    return [("us-gaap", c) for c in concepts]


def quarterly_flow(cf: dict, concepts) -> pd.DataFrame:
    """Valeurs trimestrielles (≈ 90 jours) datées du dépôt ; le T4 est déduit de l'annuel moins les trois
    trimestres déjà publiés. Les déposants de 20-F n'ont que des valeurs annuelles : on les garde alors
    telles quelles (période de 12 mois = déjà un « TTM »), avec l'attribut annual_only. Colonnes : end, filed, val."""
    annual_fallback = None
    for taxonomy, concept in _iter_concepts(concepts):
        df = _facts(cf, taxonomy, concept)
        if df.empty or df["start"].isna().all():
            continue
        df = df.dropna(subset=["start"])
        df["days"] = (df["end"] - df["start"]).dt.days
        q = _first_reported(df[(df["days"] >= 80) & (df["days"] <= 100)], ["end"])
        a = _first_reported(df[(df["days"] >= 350) & (df["days"] <= 380)], ["end"])
        rows = [{"end": r.end, "filed": r.filed, "val": float(r.val)} for r in q.itertuples()]
        q_by_end = {r.end: float(r.val) for r in q.itertuples()}
        for r in a.itertuples():
            # trimestres de l'exercice : fins de trimestre dans les 12 mois précédant la fin d'exercice
            prev = [e for e in q_by_end if r.start < e < r.end]
            if len(prev) == 3 and r.end not in q_by_end:
                rows.append({"end": r.end, "filed": r.filed, "val": float(r.val) - sum(q_by_end[e] for e in prev)})
        out = pd.DataFrame(rows).sort_values(["end", "filed"]).drop_duplicates("end", keep="first") if rows else pd.DataFrame(columns=["end", "filed", "val"])
        if len(out) >= 8:
            out.attrs["concept"] = f"{taxonomy}:{concept}"
            out.attrs["unit"] = df["unit"].iloc[0]
            return out.reset_index(drop=True)
        if annual_fallback is None and len(a) >= 4:
            ann = a[["end", "filed", "val"]].copy()
            ann["val"] = ann["val"].astype(float)
            ann.attrs["concept"] = f"{taxonomy}:{concept}"
            ann.attrs["unit"] = df["unit"].iloc[0]
            ann.attrs["annual_only"] = True
            annual_fallback = ann.sort_values("end").reset_index(drop=True)
    if annual_fallback is not None:
        return annual_fallback
    return pd.DataFrame(columns=["end", "filed", "val"])


def instant(cf: dict, concepts, taxonomy: str | None = None) -> pd.DataFrame:
    pairs = [(taxonomy, c) for c in concepts] if taxonomy else _iter_concepts(concepts)
    for tax, concept in pairs:
        df = _facts(cf, tax, concept)
        if df.empty:
            continue
        out = _first_reported(df, ["end"])[["end", "filed", "val"]].sort_values("end")
        if len(out) >= 4:
            out.attrs["concept"] = f"{tax}:{concept}"
            out.attrs["unit"] = df["unit"].iloc[0]
            return out.reset_index(drop=True)
    return pd.DataFrame(columns=["end", "filed", "val"])


def ttm(q: pd.DataFrame) -> pd.DataFrame:
    """Somme glissante des 4 derniers trimestres, datée du dépôt du plus récent (valeurs annuelles : inchangées)."""
    if q.empty or q.attrs.get("annual_only"):
        return q
    q = q.sort_values("end").reset_index(drop=True)
    q["ttm"] = q["val"].rolling(4, min_periods=4).sum()
    # un TTM n'est connu que lorsque ses 4 trimestres sont déposés
    filed_ns = pd.to_datetime(q["filed"]).astype("datetime64[ns]").astype("int64").astype("float64")
    q["filed_ttm"] = pd.to_datetime(filed_ns.rolling(4, min_periods=4).max())
    out = q.dropna(subset=["ttm"])[["end", "filed_ttm", "ttm"]].rename(columns={"filed_ttm": "filed", "ttm": "val"})
    return out.reset_index(drop=True)


def fundamentals(cik: int) -> dict[str, pd.DataFrame]:
    """Toutes les séries (TTM pour les flux, dernière valeur pour les stocks), chacune avec end/filed/val."""
    cf = fetch_companyfacts(cik)
    out = {}
    for key, (concepts, kind) in CONCEPTS.items():
        if kind == "flow":
            q = quarterly_flow(cf, concepts)
            t = ttm(q)
            t.attrs.update(q.attrs)
            out[key] = t
        else:
            out[key] = instant(cf, concepts)
    out["shares"] = instant(cf, SHARES_CONCEPTS, taxonomy="dei")
    units = {v.attrs.get("unit") for v in out.values() if v.attrs.get("unit") and v.attrs.get("unit") != "shares"}
    if len(units) > 1:
        log.warning("CIK %d : plusieurs devises dans les comptes (%s) ; vérifier la cohérence avec la devise du cours", cik, units)
    log.info("EDGAR CIK %d : %s%s", cik, ", ".join(f"{k}={len(v)}" for k, v in out.items()),
             " (annuel seulement : déposant 20-F)" if any(v.attrs.get("annual_only") for v in out.values()) else "")
    return out
