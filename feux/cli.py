from __future__ import annotations

import argparse
import logging
import sys

from .config import rules

log = logging.getLogger("feux")


def cmd_update(args) -> None:
    from .loaders import alternative_me, coinmetrics, deribit, finra, fred, shiller, yahoo

    r = rules()
    steps = {
        "shiller": shiller.update,
        "fred": fred.update,
        "yahoo": lambda: yahoo.update(r["indices"]["assets"], extra={"vix_yahoo": "^VIX", **{f"theme_{k}": v["ticker"] for k, v in r["themes"]["assets"].items()}}),
        "coinmetrics": coinmetrics.update,
        "fng": alternative_me.update,
        "deribit": deribit.update,
        "finra": finra.update,
    }
    only = set(args.only.split(",")) if args.only else set(steps)
    failures = []
    for name, fn in steps.items():
        if name not in only:
            continue
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            log.exception("Échec du chargeur %s : %s", name, exc)
            failures.append(name)
    if failures:
        log.error("Chargeurs en échec : %s", ", ".join(failures))
        if args.strict:
            sys.exit(1)


def cmd_signals(args) -> None:
    from .signals import compute_all, save_signals
    from .themes import compute_all as themes_all, save_all as themes_save

    res = compute_all()
    save_signals(res)
    themes_save(themes_all())
    for asset, df in res.items():
        last = df.dropna(subset=["color"]).iloc[-1]
        log.info("%-8s %s  couleur=%s  V=%.0f X=%.0f E=%s P=%s dd=%.1f%% levier=%s",
                 asset, last.name.date(), last["color"], last.get("V", float("nan")), last.get("X", float("nan")),
                 f"{last['E']:.0f}" if "E" in last and last["E"] == last["E"] else "–",
                 f"{last['P']:.0f}" if "P" in last and last["P"] == last["P"] else "–",
                 100 * last["drawdown"], last["trend_broken"])


def cmd_backtest(args) -> None:
    from .backtest import run_all

    run_all()


def cmd_brief(args) -> None:
    from .brief import run

    run(dry_run=args.dry_run)


def cmd_themes(args) -> None:
    from .themes import compute_all, save_all

    save_all(compute_all())


def cmd_universe(args) -> None:
    from .universe import build

    build(top=args.top)


def cmd_stocks(args) -> None:
    from .stocks import compute_all, save_all

    res = compute_all(limit=args.limit)
    save_all(res)


def cmd_decide(args) -> None:
    from . import journal

    def ask_answers() -> list[str]:
        if args.answers:
            parts = [a.strip() for a in args.answers.split("|")]
            if len(parts) == len(journal.QUESTIONS):
                return parts
        print("Répondez par écrit aux cinq questions :")
        return [input(f"  {q} ") for q in journal.QUESTIONS]

    if args.what == "new":
        rates = journal.base_rates(args.asset)
        if rates:
            print("Avant d'enregistrer, ce que l'histoire dit de cette situation :")
            print("  " + rates)
        item = journal.new(args.asset, args.action, args.amount, args.thesis or "", args.invalidation or "", ask_answers())
        print(f"Intention {item['id']} enregistrée. Confirmation possible après 48 h : python -m feux decide confirm {item['id']}")
    elif args.what == "confirm":
        try:
            item = journal.confirm(args.id, ask_answers())
            print(f"Intention {item['id']} confirmée. L'ordre peut être passé manuellement chez le courtier.")
        except PermissionError as exc:
            print(f"REFUSÉ — {exc}")
            sys.exit(2)
    elif args.what == "cancel":
        journal.cancel(args.id, args.why or "")
        print("Intention annulée.")
    else:
        for i in journal.pending():
            print(f"{i['id']}  {i['created']}  {i['action']} {i['asset']} {i['amount']:,.0f} €  [{i['status']}]")


def cmd_robustness(args) -> None:
    from .robustness import run_all

    run_all()


def cmd_dashboard(args) -> None:
    from .app import build

    build()
    log.info("Application : %s", "docs/index.html")


def cmd_alert(args) -> None:
    from .alerts import notify_changes

    notify_changes(dry_run=args.dry_run)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="feux", description="Feux tricolores d'investissement long terme")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("update", help="télécharger les données")
    s.add_argument("--only", help="liste de chargeurs séparés par des virgules")
    s.add_argument("--strict", action="store_true", help="code de sortie 1 si un chargeur échoue")
    s.set_defaults(fn=cmd_update)
    s = sub.add_parser("signals", help="calculer indicateurs et couleurs")
    s.set_defaults(fn=cmd_signals)
    s = sub.add_parser("backtest", help="validation point-in-time")
    s.set_defaults(fn=cmd_backtest)
    s = sub.add_parser("brief", help="brief mensuel en langage courant (Telegram)")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_brief)
    s = sub.add_parser("themes", help="secteurs et thèmes : drapeaux de prix des ETF (11 secteurs GICS, SOX, IGV)")
    s.set_defaults(fn=cmd_themes)
    s = sub.add_parser("universe", help="univers Top 100 mondial (positions SPDR MSCI ACWI) et correspondances")
    s.add_argument("--top", type=int, default=100)
    s.set_defaults(fn=cmd_universe)
    s = sub.add_parser("stocks", help="module actions : univers Top 100 + stocks.yaml (EDGAR + prix)")
    s.add_argument("--limit", type=int, help="ne traiter que les N premières sociétés (tests)")
    s.set_defaults(fn=cmd_stocks)
    s = sub.add_parser("decide", help="journal de décision : intention → 48 h → confirmation")
    s.add_argument("what", choices=["new", "list", "confirm", "cancel"])
    s.add_argument("--asset", help="sp500, ndx, world, btc ou clé de stocks.yaml")
    s.add_argument("--action", choices=["acheter", "vendre", "arbitrer"], default="acheter")
    s.add_argument("--amount", type=float, default=0.0)
    s.add_argument("--thesis")
    s.add_argument("--invalidation", help="ce qui invaliderait la décision")
    s.add_argument("--answers", help="cinq réponses séparées par | (sinon saisie interactive)")
    s.add_argument("--id")
    s.add_argument("--why")
    s.set_defaults(fn=cmd_decide)
    s = sub.add_parser("robustness", help="sous-périodes, bootstrap, sensibilité, confirmation")
    s.set_defaults(fn=cmd_robustness)
    s = sub.add_parser("dashboard", help="générer docs/index.html")
    s.set_defaults(fn=cmd_dashboard)
    s = sub.add_parser("alert", help="alerter si une couleur ou un drapeau a changé")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_alert)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    args.fn(args)
