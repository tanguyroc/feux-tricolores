"""Brief mensuel : le point du 1er du mois, en langage courant, avec les actions concrètes du mois."""
from __future__ import annotations

import datetime as dt
import logging

from .alerts import current_state, send_telegram
from .config import DOCS_DIR
from .plain import headline, monthly_actions, simple_btc, simple_index
from .signals import load_signals
from .themes import load_all as themes_all, simple_sentence

log = logging.getLogger("feux.brief")


def compose() -> str:
    cur = current_state()
    rows = {k: load_signals(k).iloc[-1] for k in cur}
    today = dt.date.today().strftime("%d/%m/%Y")
    lines = [f"🗓️ Feux tricolores — le point du {today}", "", headline(cur), ""]
    for k, c in cur.items():
        lines.append(simple_btc(rows[k]) if k == "btc" else simple_index(k, rows[k]))
    th = themes_all()
    if th:
        lines += ["", "Vos thèmes :"] + [f"• {simple_sentence(k, df.iloc[-1])}" for k, df in th.items()]
    lines += ["", "Ce mois-ci, concrètement :"] + [f"• {a}" for a in monthly_actions(cur)]
    lines += ["", "À vérifier ce mois-ci : la clôture mensuelle de chaque indice contre sa moyenne 10 mois (drapeau levier), et l'écart de votre répartition "
              "à la cible (bandes de rééquilibrage).", "Rappel : un feu décrit un état, pas une prévision ; les versements programmés ne s'arrêtent jamais."]
    return "\n".join(lines)


def run(dry_run: bool = False) -> str:
    text = compose()
    (DOCS_DIR / "brief.md").write_text(text, encoding="utf-8")
    log.info("Brief :\n%s", text)
    if not dry_run:
        send_telegram(text)
    return text
