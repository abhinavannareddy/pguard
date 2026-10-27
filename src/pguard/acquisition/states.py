"""Labeled-state test (PRD Phase 0 step 2): can still / walking / lying be told apart?

The thresholds are starting hypotheses (the PRD says targets are revised after measurement).
shortcut: no significance test, only effect-size thresholds; upgrade once several recordings
exist to calibrate against.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from itertools import combinations

from .windows_wifi import ParseError, Sample, read_sample

REQUIRED_LABELS = ("still", "walking", "lying")
MEAN_SHIFT_DB = 1.5
STD_SHIFT_DB = 0.5
MIN_SECONDS_PER_LABEL = 5
MIN_SAMPLES_PER_LABEL = 10


class Verdict(Enum):
    PASS = "PASS"  # nosec B105
    FAIL_CONSTANT = "FAIL_CONSTANT"
    FAIL_INDISTINGUISHABLE = "FAIL_INDISTINGUISHABLE"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class StateReport:
    verdict: Verdict
    message: str
    stats: dict[str, dict[str, float]]
    separable_pairs: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict:
        return {"verdict": self.verdict.value, "message": self.message, "stats": self.stats,
                "separable_pairs": [list(p) for p in self.separable_pairs]}


def _window_stds(values: Sequence[int], size: int) -> list[float]:
    return [statistics.pstdev(values[i:i + size])
            for i in range(0, len(values) - size + 1, size)]


def analyze_states(data: dict[str, Sequence[int]], hz: float) -> StateReport:
    missing = [label for label in REQUIRED_LABELS if label not in data]
    if missing:
        raise ValueError(f"missing labels: {missing}")
    # Too little data is a fact about the recording, never a verdict about the signal.
    min_samples = max(MIN_SAMPLES_PER_LABEL, int(hz * MIN_SECONDS_PER_LABEL))
    if any(len(data[label]) < min_samples for label in REQUIRED_LABELS):
        return StateReport(Verdict.INCONCLUSIVE,
                           f"Need at least {min_samples} samples per state; check the Wi-Fi "
                           "connection and run the test again.", {}, ())
    if len({v for label in REQUIRED_LABELS for v in data[label]}) <= 1:
        return StateReport(
            Verdict.FAIL_CONSTANT,
            "The signal never changed in any state: this source cannot show motion here.",
            {}, ())
    window = max(2, round(hz))
    stats = {}
    for label in REQUIRED_LABELS:
        stds = _window_stds(data[label], window)
        stats[label] = {"n": float(len(data[label])),
                        "mean_dbm": round(statistics.fmean(data[label]), 3),
                        "median_window_std": round(statistics.median(stds), 3)}
    pairs = tuple(
        (a, b) for a, b in combinations(REQUIRED_LABELS, 2)
        if abs(stats[a]["mean_dbm"] - stats[b]["mean_dbm"]) >= MEAN_SHIFT_DB
        or abs(stats[a]["median_window_std"] - stats[b]["median_window_std"]) >= STD_SHIFT_DB
    )
    if ("still", "walking") in pairs:
        return StateReport(Verdict.PASS, "Walking is distinguishable from standing still.",
                           stats, pairs)
    return StateReport(Verdict.FAIL_INDISTINGUISHABLE,
                       "Walking could not be told apart from standing still.", stats, pairs)


def record_states(
    labels: Sequence[str],
    seconds: float,
    interval_s: float,
    countdown_s: float,
    read: Callable[[], Sample] = read_sample,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    announce: Callable[[str], None] = print,
) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for label in labels:
        announce(f"Get ready: {label} in {countdown_s:.0f} s")
        sleep(countdown_s)
        announce(f"GO: {label} for {seconds:.0f} s")
        start, values = clock(), []
        while clock() - start < seconds:
            try:
                values.append(read().rssi_dbm)
            except ParseError:
                pass
            sleep(interval_s)
        announce(f"STOP: {label}")
        out[label] = values
    return out
