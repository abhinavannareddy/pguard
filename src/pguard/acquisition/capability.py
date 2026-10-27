"""Capability classification (PRD A1, A2, A4).

CSI is claimed only when ALL of these hold: an Intel AX200/AX210 card, Linux, and a CSI tool
actually installed. Anything else is RSSI-only, or unsupported when there is no adapter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

_CSI_CARD = re.compile(r"\bAX2[01]0\b", re.IGNORECASE)
_INTEL = re.compile(r"intel", re.IGNORECASE)

FEATURES = ("presence_motion", "inactivity_watch", "fall_candidate",
            "breathing_rate", "breathing_pause")


class Tier(Enum):
    UNSUPPORTED = 0
    RSSI_ONLY = 1
    CSI = 3


@dataclass(frozen=True)
class CapabilityReport:
    adapter: str | None
    tier: Tier
    csi: bool
    features: dict[str, bool]
    limitations: tuple[str, ...]
    blocker: str | None = None


def _features(**on: bool) -> dict[str, bool]:
    return {name: on.get(name, False) for name in FEATURES}


def classify(adapter: str | None, os_name: str, csi_tool_present: bool) -> CapabilityReport:
    if not adapter:
        return CapabilityReport(
            adapter=None, tier=Tier.UNSUPPORTED, csi=False, features=_features(),
            limitations=("No sensing source is available.",),
            blocker="no usable Wi-Fi adapter found; PGuard cannot watch this home",
        )
    csi_capable = bool(_INTEL.search(adapter) and _CSI_CARD.search(adapter))
    if csi_capable and os_name == "Linux" and csi_tool_present:
        return CapabilityReport(
            adapter=adapter, tier=Tier.CSI, csi=True,
            features=_features(presence_motion=True, inactivity_watch=True,
                               fall_candidate=True, breathing_rate=True),
            limitations=(
                "Breathing is quality-gated and unproven until the paced-breathing test is run.",
            ),
        )
    limits = ["No CSI: breathing and breathing-pause detection are unavailable.",
              "Fall candidates are coarse and research-only on signal strength alone.",
              "Covers the zone between router and laptop, not the whole home."]
    if csi_capable:
        limits.append("This card could expose CSI, but only on Linux with a CSI tool; "
                      "Windows exposes no CSI.")
    return CapabilityReport(
        adapter=adapter, tier=Tier.RSSI_ONLY, csi=False,
        features=_features(presence_motion=True, inactivity_watch=True, fall_candidate=True),
        limitations=tuple(limits),
    )
