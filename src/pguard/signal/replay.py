"""Record and replay sample streams as JSON Lines (PRD A3). Schema is validated on load."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from pathlib import Path

from ..acquisition.windows_wifi import ParseError, Sample


def save_jsonl(samples: Iterable[Sample], path: Path) -> None:
    with Path(path).open("w", encoding="utf-8") as f:
        f.writelines(
            json.dumps({"t": s.t, "rssi_dbm": s.rssi_dbm, "signal_pct": s.signal_pct}) + "\n"
            for s in samples
        )


def _parse(line: str, lineno: int) -> Sample:
    try:
        d = json.loads(line)
        t, rssi = d["t"], d["rssi_dbm"]
    except (ValueError, KeyError, TypeError) as exc:  # JSONDecodeError is a ValueError
        raise ParseError(f"line {lineno}: malformed record") from exc
    if isinstance(t, bool) or not isinstance(t, (int, float)) \
            or isinstance(rssi, bool) or not isinstance(rssi, int):
        raise ParseError(f"line {lineno}: t must be a finite number and rssi_dbm an integer")
    try:
        t = float(t)  # a huge JSON integer overflows here
    except OverflowError as exc:
        raise ParseError(f"line {lineno}: t is out of range") from exc
    if not math.isfinite(t):
        raise ParseError(f"line {lineno}: t must be a finite number")
    pct = d.get("signal_pct", 0)
    if isinstance(pct, float) and pct.is_integer():
        pct = int(pct)
    if isinstance(pct, bool) or not isinstance(pct, int) or not 0 <= pct <= 100:
        raise ParseError(f"line {lineno}: signal_pct must be a whole number from 0 to 100")
    return Sample(t=t, rssi_dbm=rssi, signal_pct=pct, adapter="replay", band="")


def load_jsonl(path: Path) -> list[Sample]:
    with Path(path).open(encoding="utf-8") as f:
        return [_parse(line, i) for i, line in enumerate(f, 1) if line.strip()]
