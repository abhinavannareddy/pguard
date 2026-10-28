"""Windowed features and data-quality scoring (PRD S1-S4, D7).

Safety rule S4: a window without enough trustworthy samples is NO_DATA or UNCERTAIN, never
QUIET. "No movement" may only be reported from data that was actually measured.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from .. import PARAMS_VERSION
from ..acquisition.windows_wifi import RSSI_MAX_DBM, RSSI_MIN_DBM, Sample

_EPS = 1e-9


class State(Enum):
    NO_DATA = "no_data"
    UNCERTAIN = "uncertain"
    QUIET = "quiet"
    MOTION = "motion"


@dataclass(frozen=True)
class Params:
    version: str = PARAMS_VERSION
    window_s: float = 2.0
    expected_hz: float = 5.0
    stale_s: float = 1.0
    min_coverage: float = 0.2
    min_quality: float = 0.5
    motion_threshold_db: float = 0.8

    def __post_init__(self) -> None:
        if self.window_s <= 0 or self.expected_hz <= 0 or self.stale_s <= 0:
            raise ValueError("window_s, expected_hz and stale_s must be positive")
        for name in ("min_coverage", "min_quality"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be within 0..1")
        if self.motion_threshold_db <= 0:
            raise ValueError("motion_threshold_db must be positive")


@dataclass(frozen=True)
class WindowFeatures:
    t_start: float
    t_end: float
    n_valid: int
    n_corrupt: int
    quality: float
    flags: tuple[str, ...]
    mean_dbm: float | None
    motion_energy: float | None
    state: State
    params_version: str


def _window(t_start: float, valid: list[Sample], corrupt: int, p: Params) -> WindowFeatures:
    t_end = t_start + p.window_s
    coverage = min(1.0, len(valid) / (p.expected_hz * p.window_s))
    received = len(valid) + corrupt
    quality = round(coverage * (1 - corrupt / received), 4) if received else 0.0
    values = [s.rssi_dbm for s in valid]
    energy = round(statistics.pstdev(values), 4) if len(values) >= 2 else None
    stale = bool(valid) and t_end - valid[-1].t > p.stale_s + _EPS
    flags = tuple(f for f, on in (
        ("no_samples", not valid), ("corrupt_samples", corrupt > 0),
        # low_coverage explains UNCERTAIN: quality never exceeds coverage, so coverage below
        # min_quality always means quality below it too.
        ("low_coverage", coverage < p.min_quality), ("stale", stale)) if on)
    if coverage < p.min_coverage:
        state = State.NO_DATA
    elif quality < p.min_quality or stale or energy is None:
        state = State.UNCERTAIN
    else:
        state = State.MOTION if energy >= p.motion_threshold_db else State.QUIET
    return WindowFeatures(
        t_start=t_start, t_end=t_end, n_valid=len(valid), n_corrupt=corrupt, quality=quality,
        flags=flags, mean_dbm=round(statistics.fmean(values), 4) if values else None,
        motion_energy=energy, state=state, params_version=p.version,
    )


DEFAULT_PARAMS = Params()


def extract(
    samples: Iterable[Sample], t0: float, t1: float, p: Params = DEFAULT_PARAMS,
) -> list[WindowFeatures]:
    n = int((t1 - t0) / p.window_s + _EPS)
    valid: list[list[Sample]] = [[] for _ in range(n)]
    corrupt = [0] * n
    for s in sorted(samples, key=lambda s: s.t):
        i = int((s.t - t0) / p.window_s + _EPS)
        if s.t < t0 or i >= n:
            continue
        if RSSI_MIN_DBM <= s.rssi_dbm <= RSSI_MAX_DBM:
            valid[i].append(s)
        else:
            corrupt[i] += 1
    return [_window(t0 + i * p.window_s, valid[i], corrupt[i], p) for i in range(n)]
