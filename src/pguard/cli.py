"""`pguard` command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .acquisition.probe import run_probe
from .acquisition.states import REQUIRED_LABELS, Verdict, analyze_states, record_states


def _probe(args: argparse.Namespace) -> int:
    report = run_probe(duration_s=args.seconds, interval_s=args.interval)
    Path(args.out).write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    d = report.to_dict()
    sys.stdout.write(
        f"tier={d['capability']['tier']} samples={d['samples']} dropouts={d['dropouts']} "
        f"hz={d['achieved_hz']} rssi_mean={d['rssi_mean']} report={args.out}\n"
    )
    blocker = d["capability"]["blocker"]
    if blocker:
        sys.stderr.write(f"BLOCKER: {blocker}\n")
        return 2
    return 0


def _announce(message: str) -> None:
    sys.stdout.write(message + "\n")
    sys.stdout.flush()
    try:
        import winsound
        winsound.Beep(880, 250)
    except (ImportError, RuntimeError):
        pass


def _states(args: argparse.Namespace) -> int:
    labels = REQUIRED_LABELS
    data = record_states(labels, args.seconds, args.interval, args.countdown,
                         announce=_announce)
    hz = sum(len(v) for v in data.values()) / (args.seconds * len(labels))
    report = analyze_states(data, hz=hz)
    out = report.to_dict() | {"achieved_hz": round(hz, 2)}
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    sys.stdout.write(f"{report.verdict.value}: {report.message}\n{json.dumps(report.stats)}\n")
    return 0 if report.verdict is Verdict.PASS else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pguard")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe", help="measure this laptop's Wi-Fi sensing capability")
    p.add_argument("--seconds", type=float, default=20.0)
    p.add_argument("--interval", type=float, default=0.1)
    p.add_argument("--out", default="probe-report.json")
    p.set_defaults(func=_probe)
    s = sub.add_parser("probe-states", help="labeled test: still vs walking vs lying")
    s.add_argument("--seconds", type=float, default=20.0)
    s.add_argument("--interval", type=float, default=0.1)
    s.add_argument("--countdown", type=float, default=8.0)
    s.add_argument("--out", default="states-report.json")
    s.set_defaults(func=_states)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
