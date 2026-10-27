"""Day-one feasibility probe (PRD Phase 0). Reports only what was measured."""

from __future__ import annotations

import platform
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass

from .capability import CapabilityReport, classify
from .windows_wifi import ParseError, Sample, read_sample


@dataclass(frozen=True)
class ProbeReport:
    duration_s: float
    interval_s: float
    samples: int
    dropouts: int
    achieved_hz: float
    rssi_mean: float | None
    rssi_stdev: float | None
    rssi_min: int | None
    rssi_max: int | None
    capability: CapabilityReport

    def to_dict(self) -> dict:
        c = self.capability
        return {
            "duration_s": self.duration_s, "interval_s": self.interval_s,
            "samples": self.samples, "dropouts": self.dropouts,
            "achieved_hz": round(self.achieved_hz, 3),
            "rssi_mean": self.rssi_mean, "rssi_stdev": self.rssi_stdev,
            "rssi_min": self.rssi_min, "rssi_max": self.rssi_max,
            "capability": {
                "adapter": c.adapter, "tier": c.tier.name, "csi": c.csi,
                "features": dict(c.features), "limitations": list(c.limitations),
                "blocker": c.blocker,
            },
        }


def run_probe(
    duration_s: float,
    interval_s: float,
    read: Callable[[], Sample] = read_sample,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    os_name: str | None = None,
    csi_tool_present: bool = False,
) -> ProbeReport:
    if duration_s <= 0 or interval_s <= 0:
        raise ValueError("duration_s and interval_s must be positive")
    start = clock()
    samples: list[Sample] = []
    dropouts = 0
    while clock() - start < duration_s:
        try:
            samples.append(read())
        except ParseError:
            dropouts += 1
        sleep(interval_s)
    elapsed = clock() - start
    rssi = [s.rssi_dbm for s in samples]
    adapter = samples[0].adapter if samples else None
    return ProbeReport(
        duration_s=duration_s, interval_s=interval_s, samples=len(samples), dropouts=dropouts,
        achieved_hz=len(samples) / elapsed if elapsed > 0 else 0.0,
        rssi_mean=round(statistics.fmean(rssi), 3) if rssi else None,
        rssi_stdev=round(statistics.pstdev(rssi), 3) if rssi else None,
        rssi_min=min(rssi) if rssi else None, rssi_max=max(rssi) if rssi else None,
        capability=classify(adapter, os_name or platform.system(), csi_tool_present),
    )
