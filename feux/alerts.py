"""Alertes : uniquement quand une couleur ou un drapeau de tendance change.

Canal : Telegram (variables d'environnement TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID). Sans ces variables,
le message est seulement écrit dans le journal. L'état précédent est conservé dans docs/state.json
(commité par le workflow), ce qui rend la détection de changement indépendante de la machine.
"""
from __future__ import annotations

import json
import logging
import os

import requests

from .config import DOCS_DIR, rules
from .explain import LABEL, conduct_text, explain_btc, explain_index
from .signals import load_signals

log = logging.getLogger("feux.alerts")
STATE_PATH = DOCS_DIR / "state.json"


def current_state() -> dict:
    r = rules()
    state = {}
    for key, spec in r["indices"]["assets"].items():
        row = load_signals(key).iloc[-1]
        state[key] = {"name": spec["name"], "color": row["color_confirmed"], "trend_broken": bool(row["trend_broken"]),
                      "falling_knife": bool(row.get("falling_knife", False)), "date": str(row.name.date())}
    row = load_signals("btc").iloc[-1]
    state["btc"] = {"name": "Bitcoin", "color": row["color_confirmed"], "trend_broken": bool(row["trend_broken"]),
                    "falling_knife": bool(row.get("falling_knife", False)), "date": str(row.name.date())}
    return state


def diff(prev: dict, cur: dict) -> list[str]:
    msgs = []
    for key, c in cur.items():
        p = prev.get(key)
        if p is None:
            continue
        if p["color"] != c["color"]:
            msgs.append(f"{c['name']} : {LABEL[p['color']]} → {LABEL[c['color']]}")
        if p["trend_broken"] != c["trend_broken"]:
            msgs.append(f"{c['name']} : tendance {'CASSÉE' if c['trend_broken'] else 'rétablie'} (moyenne 10 mois / 200 jours)")
        if p.get("falling_knife") != c.get("falling_knife") and c.get("falling_knife"):
            msgs.append(f"{c['name']} : sous-drapeau « couteau qui tombe » (achats verts par sixièmes)")
    return msgs


def compose(changes: list[str], cur: dict) -> str:
    lines = ["🚦 Feux tricolores — changement d'état", ""] + [f"• {m}" for m in changes] + [""]
    for key, c in cur.items():
        df = load_signals(key)
        row = df.iloc[-1]
        if key == "btc":
            lines.append(explain_btc(row))
        else:
            lines.append(explain_index(c["name"], row))
        lines.append("Conduite : " + " ".join(conduct_text(c["color"])))
        lines.append("")
    lines.append("Rappel : versements réguliers maintenus ; check-list et délai de 48 h avant tout ordre exceptionnel.")
    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        log.warning("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID absents : alerte non envoyée")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in [text[i:i + 3900] for i in range(0, len(text), 3900)]:
        r = requests.post(url, json={"chat_id": chat, "text": chunk, "disable_web_page_preview": True}, timeout=30)
        r.raise_for_status()
    return True


def notify_changes(dry_run: bool = False) -> list[str]:
    cur = current_state()
    prev = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    changes = diff(prev, cur)
    if changes:
        text = compose(changes, cur)
        log.info("Changements détectés :\n%s", text)
        if not dry_run:
            send_telegram(text)
    else:
        log.info("Aucun changement de couleur ni de drapeau.")
    if not dry_run:
        STATE_PATH.write_text(json.dumps(cur, indent=1, ensure_ascii=False), encoding="utf-8")
    return changes
