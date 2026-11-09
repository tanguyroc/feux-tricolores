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
from .explain import LABEL, conduct_text, conduct_text_btc, explain_btc, explain_index
from .plain import headline, monthly_actions, simple_btc, simple_index
from .signals import load_signals

log = logging.getLogger("feux.alerts")
STATE_PATH = DOCS_DIR / "state.json"


def _rows() -> dict:
    """Dernière ligne de chaque actif, complétée des champs calculés à l'enregistrement (docs/latest.json)."""
    from .dashboard import _row_with_extras

    keys = list(rules()["indices"]["assets"]) + ["btc"]
    return {k: _row_with_extras(k, load_signals(k)) for k in keys}


def current_state() -> dict:
    r = rules()
    state = {"_rules_version": str(r["version"])}
    for key, row in _rows().items():
        name = r["indices"]["assets"].get(key, {}).get("name", "Bitcoin")
        state[key] = {"name": name, "color": row["color_confirmed"], "trend_broken": bool(row["trend_broken"]),
                      "falling_knife": bool(row.get("falling_knife", False)), "cher": bool(row.get("cher", False)),
                      "cher_tendu": bool(row.get("cher_tendu", False)), "date": str(row.name.date())}
    return state


def diff(prev: dict, cur: dict) -> list[str]:
    msgs = []
    for key, c in cur.items():
        if key.startswith("_"):
            continue
        p = prev.get(key)
        if p is None:
            continue
        if p["color"] != c["color"]:
            msgs.append(f"{c['name']} : {LABEL[p['color']]} → {LABEL[c['color']]}")
        if p["trend_broken"] != c["trend_broken"]:
            msgs.append(f"{c['name']} : tendance {'CASSÉE' if c['trend_broken'] else 'rétablie'} (moyenne 10 mois / 200 jours)")
        if p.get("falling_knife") != c.get("falling_knife") and c.get("falling_knife"):
            msgs.append(f"{c['name']} : sous-drapeau « couteau qui tombe » (achats verts par sixièmes)")
        if "cher" in p and p.get("cher") != c.get("cher"):
            msgs.append(f"{c['name']} : {'devient « cher » (information)' if c.get('cher') else 'n est plus « cher »'}")
    return msgs


def compose(changes: list[str], cur: dict, detailed: bool = True) -> str:
    lines = ["🚦 Feux tricolores — changement d'état", ""] + [f"• {m}" for m in changes] + ["", headline({k: v for k, v in cur.items() if not k.startswith("_")}), ""]
    rows = _rows()
    cur = {k: v for k, v in cur.items() if not k.startswith("_")}
    for key, c in cur.items():
        lines.append(simple_btc(rows[key]) if key == "btc" else simple_index(key, rows[key]))
    lines += ["", "Ce mois-ci, concrètement :"] + [f"• {a}" for a in monthly_actions(cur)]
    if detailed:
        lines.append("")
        lines.append("— Détail chiffré —")
        for key, c in cur.items():
            lines.append(explain_btc(rows[key]) if key == "btc" else explain_index(c["name"], rows[key]))
            lines.append("Conduite : " + " ".join(conduct_text_btc(c["color"]) if key == "btc" else conduct_text(c["color"])))
            lines.append("")
    return "\n".join(lines)


def send_ntfy(text: str, title: str = "Feux tricolores") -> bool:
    """ntfy.sh : notification push sans compte. Le sujet (NTFY_TOPIC) est le seul secret : qui le connaît peut
    lire et envoyer sur ce canal, d'où un nom long et aléatoire, stocké en secret GitHub."""
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return False
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    body = text if len(text) <= 3800 else text[:3700] + "\n… (suite dans l'application)"
    r = requests.post(f"{server}/{topic}", data=body.encode("utf-8"),
                      headers={"Title": title.encode("utf-8").decode("latin-1", "ignore"), "Tags": "vertical_traffic_light", "Priority": "default",
                               "Content-Type": "text/plain; charset=utf-8"}, timeout=30)
    r.raise_for_status()
    return True


def send_telegram(text: str) -> bool:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in [text[i:i + 3900] for i in range(0, len(text), 3900)]:
        r = requests.post(url, json={"chat_id": chat, "text": chunk, "disable_web_page_preview": True}, timeout=30)
        r.raise_for_status()
    return True


def send(text: str, title: str = "Feux tricolores") -> bool:
    """Envoie sur tous les canaux configurés (ntfy et/ou Telegram) ; journalise si aucun ne l'est."""
    sent = False
    for fn in (lambda: send_ntfy(text, title), lambda: send_telegram(text)):
        try:
            sent = fn() or sent
        except Exception as exc:  # noqa: BLE001
            log.error("Envoi d'alerte en échec : %s", exc)
    if not sent:
        log.warning("Aucun canal d'alerte configuré (NTFY_TOPIC ou TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID) : message non envoyé")
    return sent


RULES_CHANGE_NOTE = {
    "1.0": ("Changement de RÈGLES (v1.0, 9 novembre 2026), pas de marché : un test publié avant calcul a montré qu'aucune règle « rouge » "
            "fondée sur la valorisation n'a fonctionné sur le S&P 500 depuis 1990 (elle fonctionnait sur 1920-1989). Les indices passent donc "
            "de rouge à orange avec l'étiquette « cher » ; le Bitcoin suit une règle en niveaux (MVRV, moyenne 200 semaines).")}


def notify_changes(dry_run: bool = False) -> list[str]:
    cur = current_state()
    prev = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    changes = diff(prev, cur)
    if changes and prev.get("_rules_version") != cur["_rules_version"] and cur["_rules_version"] in RULES_CHANGE_NOTE:
        changes = [RULES_CHANGE_NOTE[cur["_rules_version"]]] + changes
    if changes:
        text = compose(changes, cur)
        log.info("Changements détectés :\n%s", text)
        if not dry_run:
            send(text, "Feux tricolores — changement d'état")
    else:
        log.info("Aucun changement de couleur ni de drapeau.")
    if not dry_run:
        STATE_PATH.write_text(json.dumps(cur, indent=1, ensure_ascii=False), encoding="utf-8")
    return changes
