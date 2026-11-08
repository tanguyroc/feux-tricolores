"""Explication en langage clair d'un état, à partir des seules valeurs calculées (déterministe).

Un LLM peut être branché ici en option (voir runbook.md) : il ne doit citer que des valeurs présentes
dans le dictionnaire `row`, et sa sortie est contrôlée par `check_numbers`.
"""
from __future__ import annotations

import re

import pandas as pd

from .config import rules

LABEL = {"green": "VERT", "orange": "ORANGE", "red": "ROUGE"}


def _f(x, fmt="{:.0f}", suffix=""):
    try:
        if x is None or pd.isna(x):
            return "n.d."
        return fmt.format(x) + suffix
    except Exception:  # noqa: BLE001
        return "n.d."


def explain_index(name: str, row: pd.Series) -> str:
    r = rules()["indices"]
    parts = [f"{name} : {LABEL[row.get('color_confirmed', row['color'])]}."]
    if row["reason"]:
        parts.append(f"Motif : {row['reason']}.")
    parts.append(
        f"Valorisation V = {_f(row['V'])} (CAPE {_f(row['cape_live'], '{:.1f}')}, {_f(row['cape_pct'])}e percentile sur 25 ans ; "
        f"Excess CAPE Yield {_f(100 * row['ecy_live'], '{:.2f}', ' %')} ; allocation actions des ménages {_f(100 * row['aiae'], '{:.1f}', ' %')}, "
        f"{_f(row['aiae_pct'])}e percentile).")
    parts.append(
        f"Extension X = {_f(row['X'])} (écart à la moyenne 200 jours {_f(100 * row['gap_ma200'], '{:+.1f}', ' %')}, "
        f"performance 12 mois {_f(100 * row['mom_12m'], '{:+.1f}', ' %')}"
        + (" ; critère hausse ≥100 %/2 ans avec accélération ACTIF" if bool(row["gsy"]) else "") + ").")
    parts.append(
        f"Euphorie E = {_f(row['E'])} (dette sur marge {_f(100 * row['margin_yoy'], '{:+.0f}', ' %')} sur un an). "
        f"Peur P = {_f(row['P'])} (VIX {_f(row['vix'], '{:.1f}')}, spread Baa {_f(row['credit_spread'], '{:.2f}', ' pt')}). "
        f"Baisse depuis le plus haut : {_f(100 * row['drawdown'], '{:.1f}', ' %')}.")
    if bool(row["trend_broken"]):
        parts.append("Drapeau TENDANCE CASSÉE : dernière clôture mensuelle sous la moyenne 10 mois → levier ramené à 0-5 % sous 5 jours de bourse.")
    else:
        parts.append("Tendance : clôture mensuelle au-dessus de la moyenne 10 mois (levier autorisé dans la limite de la couleur).")
    if bool(row.get("falling_knife", False)):
        parts.append("Sous-drapeau COUTEAU QUI TOMBE : vert, mais prix sous la moyenne 10 mois et baisse sur 3 mois → déploiement par sixièmes sur 6 mois.")
    return " ".join(parts)


def explain_btc(row: pd.Series) -> str:
    parts = [f"Bitcoin : {LABEL[row.get('color_confirmed', row['color'])]}."]
    if row["reason"]:
        parts.append(f"Motif : {row['reason']}.")
    parts.append(
        f"Valorisation V = {_f(row['V'], '{:+.2f}')}σ (prix / moyenne 200 semaines {_f(row['ratio_200w'], '{:.2f}')}x, z {_f(row['z_ratio_200w'], '{:+.2f}')} ; "
        f"MVRV {_f(row['mvrv'], '{:.2f}')}, z {_f(row['z_mvrv'], '{:+.2f}')}).")
    parts.append(
        f"Baisse depuis le record : {_f(100 * row['drawdown'], '{:.0f}', ' %')} ; Fear & Greed moyen 30 jours {_f(row['fng_30d'])} ; "
        f"écart à la moyenne 200 jours {_f(100 * row['gap_ma200d'], '{:+.0f}', ' %')}"
        + (" ; critère hausse ≥100 %/2 ans avec accélération ACTIF" if bool(row["gsy"]) else "") + ".")
    if bool(row["trend_broken"]):
        parts.append("Tendance cassée (sous la moyenne 200 jours) : aucun proxy à levier ; achats verts par tranches.")
    return " ".join(parts)


def conduct_text(color: str) -> list[str]:
    c = rules()["conduct"][color]
    return [
        f"Versement régulier : {c['regular_contribution']}.",
        f"Montants exceptionnels / réserve : {c['reserve']}.",
        f"Levier : plafond {100 * c['leverage_cap_share_equities']:.0f} % de la poche actions"
        + (" (et seulement si la tendance est OK)" if c.get("leverage_requires_trend_ok") else "") + ".",
        f"Rééquilibrage : bandes ±{c['rebalance_band_pts']} points.",
    ]


def check_numbers(text: str, row: pd.Series, tolerance: float = 0.6) -> list[str]:
    """Vérifie que chaque nombre du texte correspond à une valeur (ou à son pourcentage) de `row`.
    Garde-fou pour une explication générée par un LLM. Renvoie la liste des nombres non retrouvés."""
    values = set()
    for v in row.values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if pd.isna(f):
            continue
        values.update([f, 100 * f, abs(f), 100 * abs(f)])
    bad = []
    for tok in re.findall(r"[-+]?\d+(?:[.,]\d+)?", text):
        n = float(tok.replace(",", "."))
        if n in (0.0, 1.0, 3.0, 5.0, 6.0, 10.0, 25.0, 30.0, 40.0, 50.0, 80.0, 90.0, 100.0, 200.0):
            continue  # seuils et constantes des règles
        if not any(abs(n - v) <= tolerance for v in values):
            bad.append(tok)
    return bad
