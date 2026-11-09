"""Brief mensuel : le point du 1er du mois, en langage courant, avec les actions concrètes du mois."""
from __future__ import annotations

import datetime as dt
import logging

from .alerts import _rows, current_state, send
from .config import DOCS_DIR
from .plain import headline, monthly_actions, simple_btc, simple_index
from .themes import load_all as themes_all, simple_sentence

log = logging.getLogger("feux.brief")


def compose() -> str:
    cur = {k: v for k, v in current_state().items() if not k.startswith("_")}
    rows = _rows()
    today = dt.date.today().strftime("%d/%m/%Y")
    lines = [f"🗓️ Feux tricolores — le point du {today}", "", headline(cur), ""]
    for k, c in cur.items():
        lines.append(simple_btc(rows[k]) if k == "btc" else simple_index(k, rows[k]))
    th = themes_all()
    flagged = [(k, df.iloc[-1]) for k, df in th.items() if bool(df.iloc[-1].get("gsy")) or bool(df.iloc[-1].get("extended"))]
    if flagged:
        lines += ["", "Secteurs et thèmes avec un drapeau actif :"] + [f"• {simple_sentence(k, row)}" for k, row in flagged]
    lines += ["", "Ce mois-ci, concrètement :"] + [f"• {a}" for a in monthly_actions(cur)]
    lines += ["", "À vérifier ce mois-ci : la clôture mensuelle de chaque indice contre sa moyenne 10 mois (drapeau levier), et l'écart de votre répartition "
              "à la cible (bandes de rééquilibrage).", "Rappel : un feu décrit un état, pas une prévision ; les versements programmés ne s'arrêtent jamais."]
    return "\n".join(lines)


def run(dry_run: bool = False) -> str:
    text = compose()
    (DOCS_DIR / "brief.md").write_text(text, encoding="utf-8")
    log.info("Brief :\n%s", text)
    if not dry_run:
        send(text, "Feux tricolores — le point du mois")
    return text
