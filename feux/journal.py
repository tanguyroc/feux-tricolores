"""Journal de décision : tout ordre exceptionnel passe par une intention écrite, cinq questions, puis une
confirmation impossible avant 48 heures. Fichier Markdown append-only (journal/decisions.md) + index JSON.

    python -m feux decide new  --asset ndx --action acheter --amount 5000 --thesis "..." --invalidation "..."
    python -m feux decide list
    python -m feux decide confirm <id>      # refusé avant 48 h, et redemande les cinq réponses
    python -m feux decide cancel <id>
"""
from __future__ import annotations

import datetime as dt
import json
import uuid

from .config import ROOT, rules

JOURNAL_DIR = ROOT / "journal"
INDEX = JOURNAL_DIR / "decisions.json"
LOG = JOURNAL_DIR / "decisions.md"
QUESTIONS = [
    "Quelle couleur, et depuis quand ?",
    "Quel drapeau de tendance ?",
    "Le montant respecte-t-il le plafond de la couleur ?",
    "Ai-je lu l'explication générée ?",
    "Agirais-je identiquement si le marché avait baissé de 10 % demain ?",
]


def _load() -> list[dict]:
    JOURNAL_DIR.mkdir(exist_ok=True)
    return json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else []


def _save(items: list[dict]) -> None:
    INDEX.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")


def _append_md(text: str) -> None:
    JOURNAL_DIR.mkdir(exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(text + "\n")


def _snapshot(asset: str) -> dict:
    """Couleur, drapeaux et motif au moment de l'intention (depuis docs/latest.json ou stocks_latest.json)."""
    from .config import DOCS_DIR

    for name in ("latest.json", "stocks_latest.json"):
        p = DOCS_DIR / name
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            if asset in data:
                d = data[asset]
                return {k: d.get(k) for k in ("date", "color", "color_confirmed", "reason", "trend_broken", "falling_knife", "V", "drawdown")}
    return {}


def base_rates(asset: str) -> str:
    """Statistiques historiques (backtest) pour la couleur actuelle de l'actif : ce qui s'est passé ensuite, en général."""
    from .config import DOCS_DIR

    p = DOCS_DIR / "backtest_summary.json"
    snap = _snapshot(asset)
    color = snap.get("color_confirmed") or snap.get("color")
    if not p.exists() or not color or asset not in json.loads(p.read_text(encoding="utf-8")):
        return ""
    s = json.loads(p.read_text(encoding="utf-8"))[asset]
    f1 = next((r for r in s["fwd"] if r["horizon"] == "1 an" and r["couleur"] == color), None)
    f3 = next((r for r in s["fwd"] if r["horizon"] == "3 ans" and r["couleur"] == color), None)
    dd = next((r for r in s["dd24"] if r["couleur"] == color), None)
    if not (f1 and f3 and dd):
        return ""
    fr = {"green": "vert", "orange": "orange", "red": "rouge"}[color]
    return (f"après un jour {fr} sur cet actif, le rendement médian a été de {100 * f1['médiane_annualisée']:+.1f} % à un an "
            f"(négatif dans {100 * f1['part_négative']:.0f} % des cas) et de {100 * f3['médiane_annualisée']:+.1f} %/an sur trois ans ; "
            f"la baisse médiane dans les 24 mois suivants a été de {100 * dd['drawdown_24m_médian']:.0f} % "
            f"(plus de 20 % dans {100 * dd['part_drawdown_>20%']:.0f} % des cas).")


def new(asset: str, action: str, amount: float, thesis: str, invalidation: str, answers: list[str]) -> dict:
    if len(answers) != len(QUESTIONS) or any(not a.strip() for a in answers):
        raise ValueError("Les cinq réponses sont obligatoires.")
    now = dt.datetime.now(dt.timezone.utc)
    item = {"id": uuid.uuid4().hex[:8], "created": now.isoformat(timespec="minutes"), "asset": asset, "action": action,
            "amount": amount, "thesis": thesis, "invalidation": invalidation,
            "answers": dict(zip(QUESTIONS, answers)), "snapshot": _snapshot(asset), "base_rates": base_rates(asset), "status": "en attente"}
    items = _load()
    items.append(item)
    _save(items)
    _append_md(f"\n## {item['created']} — intention {item['id']} : {action} {asset} {amount:,.0f} €\n"
               f"- État au moment de l'intention : {json.dumps(item['snapshot'], ensure_ascii=False)}\n- Thèse : {thesis}\n- Invalidation : {invalidation}\n"
               + "\n".join(f"- {q} → {a}" for q, a in item["answers"].items()))
    return item


def confirm(item_id: str, answers: list[str]) -> dict:
    hours = int(rules()["conduct"]["exceptional_order_checklist_hours"])
    items = _load()
    for item in items:
        if item["id"] == item_id:
            created = dt.datetime.fromisoformat(item["created"])
            now = dt.datetime.now(dt.timezone.utc)
            elapsed = (now - created).total_seconds() / 3600
            if elapsed < hours:
                raise PermissionError(f"Délai non écoulé : {elapsed:.1f} h sur {hours} h. Confirmation possible à partir de "
                                      f"{(created + dt.timedelta(hours=hours)).astimezone().strftime('%d/%m/%Y %H:%M')}.")
            if len(answers) != len(QUESTIONS) or any(not a.strip() for a in answers):
                raise ValueError("Les cinq réponses sont redemandées à la confirmation.")
            item["status"] = "confirmé"
            item["confirmed"] = now.isoformat(timespec="minutes")
            item["answers_confirmation"] = dict(zip(QUESTIONS, answers))
            item["snapshot_confirmation"] = _snapshot(item["asset"])
            _save(items)
            _append_md(f"\n### {item['confirmed']} — confirmation {item_id} après {elapsed:.0f} h\n"
                       f"- État à la confirmation : {json.dumps(item['snapshot_confirmation'], ensure_ascii=False)}\n"
                       + "\n".join(f"- {q} → {a}" for q, a in item["answers_confirmation"].items()))
            return item
    raise KeyError(f"Intention {item_id} introuvable.")


def cancel(item_id: str, why: str = "") -> dict:
    items = _load()
    for item in items:
        if item["id"] == item_id:
            item["status"] = "annulé"
            item["cancelled"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
            _save(items)
            _append_md(f"\n### {item['cancelled']} — annulation {item_id} : {why}")
            return item
    raise KeyError(f"Intention {item_id} introuvable.")


def pending() -> list[dict]:
    return [i for i in _load() if i["status"] == "en attente"]
