"""Record and replay sample streams as JSON Lines (PRD A3). Schema is validated on load."""

from __future__ import annotations

import json
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
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ParseError(f"line {lineno}: malformed record") from exc
    if isinstance(t, bool) or not isinstance(t, (int, float)) \
            or isinstance(rssi, bool) or not isinstance(rssi, int):
        raise ParseError(f"line {lineno}: t must be a number and rssi_dbm an integer")
    return Sample(t=float(t), rssi_dbm=rssi, signal_pct=int(d.get("signal_pct", 0)),
                  adapter="replay", band="")


def load_jsonl(path: Path) -> list[Sample]:
    with Path(path).open(encoding="utf-8") as f:
        return [_parse(line, i) for i, line in enumerate(f, 1) if line.strip()]
