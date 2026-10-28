"""`pguard` command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .acquisition.probe import run_probe
from .acquisition.states import REQUIRED_LABELS, Verdict, analyze_states, record_states
from .signal.features import Params, State, extract
from .signal.synth import generate


def _number(raw: str, minimum_exclusive: bool) -> float:
    try:
        value = float(raw)
    except ValueError:
        value = float("nan")
    ok = value > 0 if minimum_exclusive else value >= 0
    if not ok or value == float("inf"):
        word = "positive" if minimum_exclusive else "non-negative"
        raise argparse.ArgumentTypeError(f"{raw!r} must be a {word} number")
    return value


def _positive(raw: str) -> float:
    return _number(raw, minimum_exclusive=True)


def _non_negative(raw: str) -> float:
    return _number(raw, minimum_exclusive=False)


def _writable(path: str) -> bool:
    """Fail before a long recording, not after it."""
    try:
        with Path(path).open("a", encoding="utf-8"):
            pass
    except OSError as exc:
        sys.stderr.write(f"cannot write report to {path}: {exc.strerror or exc}\n")
        return False
    return True


def _write_json(path: str, data: dict) -> bool:
    try:
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"cannot write report to {path}: {exc.strerror or exc}\n")
        return False
    return True


def _probe(args: argparse.Namespace) -> int:
    if not _writable(args.out):
        return 1
    report = run_probe(duration_s=args.seconds, interval_s=args.interval)
    d = report.to_dict()
    if not _write_json(args.out, d):
        return 1
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
    if not _writable(args.out):
        return 1
    labels = REQUIRED_LABELS
    data = record_states(labels, args.seconds, args.interval, args.countdown,
                         announce=_announce)
    hz = sum(len(v) for v in data.values()) / (args.seconds * len(labels))
    report = analyze_states(data, hz=hz)
    out = report.to_dict() | {"achieved_hz": round(hz, 2)}
    if not _write_json(args.out, out):
        return 1
    sys.stdout.write(f"{report.verdict.value}: {report.message}\n{json.dumps(report.stats)}\n")
    return 0 if report.verdict is Verdict.PASS else 3


_SYMBOLS = {State.QUIET: "Q", State.MOTION: "M", State.UNCERTAIN: "?", State.NO_DATA: "."}


def _demo(args: argparse.Namespace) -> int:
    """Run the pipeline on synthetic data: still, walking, still, a dropout, a weak link."""
    a = args.seconds / 6
    scenario = [("still", a), ("walking", a), ("still", a), ("still", a), ("still", a),
                ("still", a)]
    samples = [
        x for x in generate(scenario, hz=5.0, seed=args.seed)
        if not 3 * a <= x.t < 4 * a                      # sensor dropout
        and (not 4 * a <= x.t < 5 * a or round(x.t * 5) % 5 == 0)  # weak link
    ]
    windows = extract(samples, 0, args.seconds, Params())
    counts = {s: sum(w.state is s for w in windows) for s in State}
    out = sys.stdout.write
    out("SYNTHETIC DEMO: generated data, not a measurement of any home.\n")
    out("".join(_SYMBOLS[w.state] for w in windows) + "\n")
    out("  ".join(f"{_SYMBOLS[s]}={s.value}({n})" for s, n in counts.items()) + "\n")
    out("A gap or weak link is shown as no_data/uncertain, never as quiet.\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pguard")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe", help="measure this laptop's Wi-Fi sensing capability")
    p.add_argument("--seconds", type=_positive, default=20.0)
    p.add_argument("--interval", type=_positive, default=0.1)
    p.add_argument("--out", default="probe-report.json")
    p.set_defaults(func=_probe)
    s = sub.add_parser("probe-states", help="labeled test: still vs walking vs lying")
    s.add_argument("--seconds", type=_positive, default=20.0)
    s.add_argument("--interval", type=_positive, default=0.1)
    s.add_argument("--countdown", type=_non_negative, default=8.0)
    s.add_argument("--out", default="states-report.json")
    s.set_defaults(func=_states)
    d = sub.add_parser("demo", help="run the pipeline on synthetic data (works on any OS)")
    d.add_argument("--seconds", type=_positive, default=120.0)
    d.add_argument("--seed", type=int, default=1)
    d.set_defaults(func=_demo)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
