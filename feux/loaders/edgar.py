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

import pandas as pd

from ..config import RAW_DIR
from . import http_get, log

URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# Concepts us-gaap par ordre de préférence. flow = sur une période ; instant = à une date.
CONCEPTS = {
    "revenue": (["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"], "flow"),
    "ebit": (["OperatingIncomeLoss"], "flow"),
    "net_income": (["NetIncomeLoss"], "flow"),
    "cfo": (["NetCashProvidedByUsedInOperatingActivities"], "flow"),
    "capex": (["PaymentsToAcquirePropertyPlantAndEquipment"], "flow"),
    "da": (["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "DepreciationAmortizationAndAccretionNet"], "flow"),
    "cash": (["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"], "instant"),
    "st_investments": (["ShortTermInvestments", "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"], "instant"),
    "debt_lt": (["LongTermDebtNoncurrent", "LongTermDebt"], "instant"),
    "debt_st": (["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"], "instant"),
    "equity": (["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"], "instant"),
}
SHARES_CONCEPTS = ["EntityCommonStockSharesOutstanding"]  # taxonomie dei


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
        if unit not in ("USD", "shares"):
            continue
        for f in lst:
            if f.get("form") not in ("10-K", "10-Q", "10-K/A", "10-Q/A", "20-F", "40-F"):
                continue
            rows.append({"start": f.get("start"), "end": f["end"], "val": f["val"], "filed": f["filed"],
                         "fy": f.get("fy"), "fp": f.get("fp"), "form": f["form"]})
    if not rows:
        return pd.DataFrame(columns=["start", "end", "val", "filed", "fy", "fp", "form"])
    df = pd.DataFrame(rows)
    for c in ("start", "end", "filed"):
        df[c] = pd.to_datetime(df[c])
    return df


def _first_reported(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Pour une même période, garder la première publication (point-in-time, sans restatement)."""
    return df.sort_values("filed").drop_duplicates(keys, keep="first")


def quarterly_flow(cf: dict, concepts: list[str]) -> pd.DataFrame:
    """Valeurs trimestrielles (≈ 90 jours) datées du dépôt ; le T4 est déduit de l'annuel moins les trois
    trimestres déjà publiés. Colonnes : end, filed, val."""
    for concept in concepts:
        df = _facts(cf, "us-gaap", concept)
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
        out = pd.DataFrame(rows).sort_values(["end", "filed"]).drop_duplicates("end", keep="first")
        if len(out) >= 8:
            out.attrs["concept"] = concept
            return out.reset_index(drop=True)
    return pd.DataFrame(columns=["end", "filed", "val"])


def instant(cf: dict, concepts: list[str], taxonomy: str = "us-gaap") -> pd.DataFrame:
    for concept in concepts:
        df = _facts(cf, taxonomy, concept)
        if df.empty:
            continue
        out = _first_reported(df, ["end"])[["end", "filed", "val"]].sort_values("end")
        if len(out) >= 4:
            out.attrs["concept"] = concept
            return out.reset_index(drop=True)
    return pd.DataFrame(columns=["end", "filed", "val"])


def ttm(q: pd.DataFrame) -> pd.DataFrame:
    """Somme glissante des 4 derniers trimestres, datée du dépôt du plus récent."""
    if q.empty:
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
            out[key] = ttm(quarterly_flow(cf, concepts))
        else:
            out[key] = instant(cf, concepts)
    out["shares"] = instant(cf, SHARES_CONCEPTS, taxonomy="dei")
    log.info("EDGAR CIK %d : %s", cik, ", ".join(f"{k}={len(v)}" for k, v in out.items()))
    return out
