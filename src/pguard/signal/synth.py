"""Synthetic RSSI scenarios for development (PRD A3). Always labelled synthetic, never evidence
that PGuard works in a real home."""

from __future__ import annotations

import random
from collections.abc import Sequence

from ..acquisition.windows_wifi import Sample

BASE_DBM = -41
NOISE_DB = {"empty": 0.25, "still": 0.25, "lying": 0.25, "walking": 3.0}


def generate(scenario: Sequence[tuple[str, float]], hz: float, seed: int) -> list[Sample]:
    # Seeded for reproducible test data; not used for security.
    rng = random.Random(seed)  # nosec B311
    out: list[Sample] = []
    for label, seconds in scenario:
        if label not in NOISE_DB:
            raise ValueError(f"unknown scenario {label!r}; expected one of {sorted(NOISE_DB)}")
        for _ in range(round(seconds * hz)):
            rssi = round(BASE_DBM + rng.gauss(0, NOISE_DB[label]))
            out.append(Sample(t=round(len(out) / hz, 6), rssi_dbm=rssi, signal_pct=90,
                              adapter="synthetic", band=""))
    return out
