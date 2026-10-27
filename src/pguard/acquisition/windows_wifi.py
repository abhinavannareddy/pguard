"""Windows Wi-Fi signal acquisition via `netsh wlan show interfaces`.

Only signal-quality fields are kept. SSID, BSSID and MAC address are discarded at the
boundary so they can never reach storage, logs or alerts.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass

NETSH_TIMEOUT_S = 5.0
RSSI_MIN_DBM, RSSI_MAX_DBM = -120, -1


class ParseError(ValueError):
    """No trustworthy sample could be produced. Callers must treat this as 'no data'."""


@dataclass(frozen=True)
class Sample:
    t: float
    rssi_dbm: int
    signal_pct: int
    adapter: str
    band: str


def _fields(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            out.setdefault(key.strip().lower(), value.strip())
    return out


def _int(raw: str | None, name: str) -> int:
    try:
        return int((raw or "").rstrip("% ").strip())
    except ValueError:
        raise ParseError(f"missing or non-numeric {name}") from None


def parse_netsh(text: str, t: float) -> Sample:
    f = _fields(text)
    if f.get("state", "").lower() != "connected":
        raise ParseError("Wi-Fi interface is not connected")
    rssi = _int(f.get("rssi"), "rssi")
    if not RSSI_MIN_DBM <= rssi <= RSSI_MAX_DBM:
        raise ParseError(f"rssi {rssi} dBm outside plausible range")
    pct = _int(f.get("signal"), "signal")
    if not 0 <= pct <= 100:
        raise ParseError(f"signal {pct}% outside 0-100")
    return Sample(t=t, rssi_dbm=rssi, signal_pct=pct,
                  adapter=f.get("description", ""), band=f.get("band", ""))


def _run_netsh() -> str:
    return subprocess.run(  # fixed argv, no shell, no user input
        ["netsh", "wlan", "show", "interfaces"],
        capture_output=True, text=True, timeout=NETSH_TIMEOUT_S, check=True,
    ).stdout


def read_sample(
    runner: Callable[[], str] = _run_netsh,
    clock: Callable[[], float] = time.time,
) -> Sample:
    try:
        text = runner()
    except (OSError, subprocess.SubprocessError) as exc:
        raise ParseError(f"could not run netsh: {exc}") from exc
    return parse_netsh(text, t=clock())
