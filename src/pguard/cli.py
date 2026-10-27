"""`pguard` command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .acquisition.probe import run_probe


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pguard")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe", help="measure this laptop's Wi-Fi sensing capability")
    p.add_argument("--seconds", type=float, default=20.0)
    p.add_argument("--interval", type=float, default=0.1)
    p.add_argument("--out", default="probe-report.json")
    p.set_defaults(func=_probe)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
