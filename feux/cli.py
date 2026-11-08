from __future__ import annotations

import argparse
import logging
import sys

from .config import rules

log = logging.getLogger("feux")


def cmd_update(args) -> None:
    from .loaders import alternative_me, coinmetrics, finra, fred, shiller, yahoo

    r = rules()
    steps = {
        "shiller": shiller.update,
        "fred": fred.update,
        "yahoo": lambda: yahoo.update(r["indices"]["assets"], extra={"vix_yahoo": "^VIX"}),
        "coinmetrics": coinmetrics.update,
        "fng": alternative_me.update,
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

    res = compute_all()
    save_signals(res)
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


def cmd_dashboard(args) -> None:
    from .dashboard import build

    build()


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
    s = sub.add_parser("dashboard", help="générer docs/index.html")
    s.set_defaults(fn=cmd_dashboard)
    s = sub.add_parser("alert", help="alerter si une couleur ou un drapeau a changé")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_alert)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    args.fn(args)
