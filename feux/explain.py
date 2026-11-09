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
    """v1.0 : la couleur ne dépend que de la valorisation en niveau et de la capitulation ; le reste est du contexte."""
    parts = [f"{name} : {LABEL[row.get('color_confirmed', row['color'])]}."]
    if row["reason"]:
        parts.append(f"Motif : {row['reason']}.")
    proxy = " (mesurée sur le S&P 500 : proxy)" if bool(row.get("valuation_is_proxy", False)) else ""
    parts.append(
        f"Valorisation V = {_f(row['V'])}e percentile{proxy} : CAPE {_f(row['cape_live'], '{:.1f}')} comparé à tous les mois depuis 1881. "
        f"Rendement réel attendu à 10 ans selon le CAPE : {_f(100 * row.get('er10'), '{:+.1f}', ' %/an')} "
        f"(fourchette 80 % : {_f(100 * row.get('er10_lo'), '{:+.1f}')} à {_f(100 * row.get('er10_hi'), '{:+.1f}', ' %')} ; "
        f"depuis 1990 ce modèle a été trop pessimiste d'environ 5 points par an).")
    parts.append(
        f"Contexte, hors règle : excess CAPE yield {_f(100 * row['ecy_live'], '{:.2f}', ' %')} ; allocation actions des ménages "
        f"{_f(100 * row['aiae'], '{:.1f}', ' %')} ; écart à la moyenne 200 jours {_f(100 * row['gap_ma200'], '{:+.1f}', ' %')} "
        f"({_f(row.get('x_hist_pct'))}e percentile) ; performance 12 mois {_f(100 * row['mom_12m'], '{:+.1f}', ' %')} ; "
        f"dette sur marge {_f(100 * row['margin_yoy'], '{:+.0f}', ' %')} sur un an"
        + (" ; hausse ≥ 100 % en deux ans avec accélération" if bool(row["gsy"]) else "") + ".")
    parts.append(
        f"Peur P = {_f(row['P'])} (VIX {_f(row['vix'], '{:.1f}')}, spread Baa {_f(row['credit_spread'], '{:.2f}', ' pt')}). "
        f"Baisse depuis le plus haut : {_f(100 * row['drawdown'], '{:.1f}', ' %')}.")
    if bool(row["trend_broken"]):
        parts.append("Drapeau TENDANCE CASSÉE : dernière clôture mensuelle sous la moyenne 10 mois → levier ramené à 5 % au plus sous 5 jours de bourse.")
    else:
        parts.append("Tendance : clôture mensuelle au-dessus de la moyenne 10 mois (levier autorisé dans la limite de la couleur).")
    if bool(row.get("falling_knife", False)):
        parts.append("Sous-drapeau COUTEAU QUI TOMBE : vert, mais prix sous la moyenne 10 mois et baisse sur 3 mois → déploiement par sixièmes sur 6 mois.")
    return fr_num(" ".join(parts))


def explain_btc(row: pd.Series) -> str:
    b = rules()["bitcoin"]
    parts = [f"Bitcoin : {LABEL[row.get('color_confirmed', row['color'])]}."]
    if row["reason"]:
        parts.append(f"Motif : {row['reason']}.")
    parts.append(
        f"Règle (niveaux) : vert si MVRV < {b['green']['mvrv_max']:g} ou prix sous sa moyenne 200 semaines ; rouge si MVRV ≥ {b['red']['mvrv_min']:g}. "
        f"Aujourd'hui : MVRV {_f(row['mvrv'], '{:.2f}')}, prix à {_f(row['ratio_200w'], '{:.2f}')}× sa moyenne 200 semaines.")
    parts.append(
        f"Contexte, hors règle : z-scores 4 ans {_f(row['z_ratio_200w'], '{:+.2f}')} et {_f(row['z_mvrv'], '{:+.2f}')} ; "
        f"baisse depuis le record {_f(100 * row['drawdown'], '{:.0f}', ' %')} ; Fear & Greed moyen 30 jours {_f(row['fng_30d'])} ; "
        f"financement des perpétuels {_f(row.get('funding_pct'))}e percentile ; écart à la moyenne 200 jours {_f(100 * row['gap_ma200d'], '{:+.0f}', ' %')}"
        + (" ; hausse ≥ 100 % en deux ans avec accélération" if bool(row["gsy"]) else "") + ".")
    parts.append("Limite : le MVRV n'a pas atteint 3 aux sommets de novembre 2021 (2,72), mars 2024 (2,68) et octobre 2025 (2,29) : "
                 "le rouge peut manquer le prochain sommet.")
    if bool(row["trend_broken"]):
        parts.append("Tendance cassée (sous la moyenne 200 jours) : aucun proxy à levier ; achats verts par tranches.")
    return fr_num(" ".join(parts))


def conduct_text(color: str) -> list[str]:
    c = rules()["conduct"][color]
    return [
        f"Versement régulier : {c['regular_contribution']}.",
        f"Montants exceptionnels / réserve : {c['reserve']}.",
        f"Levier : plafond {100 * c['leverage_cap_share_equities']:.0f} % de la poche actions"
        + (f" si la tendance est OK ; {100 * rules()['conduct']['trend_broken']['leverage_cap_share_equities']:.0f} % si elle est cassée"
           if c.get("leverage_requires_trend_ok") else "") + ".",
        f"Rééquilibrage : bandes ±{c['rebalance_band_pts']} points.",
    ]


def conduct_text_btc(color: str) -> list[str]:
    return [f"Bitcoin ({LABEL[color].lower()}) : {rules()['conduct']['bitcoin'][color]}."]


def fr_num(text: str) -> str:
    """Virgule décimale française dans un texte (« 1.12× » → « 1,12× ») sans toucher « v1.0 » ni les identifiants."""
    return re.sub(r"(?<![\w.])([+\-−]?\d+)\.(\d+)(?![\w.])", r"\1,\2", text)


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
