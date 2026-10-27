"""Windows Wi-Fi signal acquisition via `netsh wlan show interfaces`.

Only signal-quality fields are kept. SSID, BSSID and MAC address are discarded at the
boundary so they can never reach storage, logs or alerts.
"""

from __future__ import annotations

import os

# subprocess only runs netsh with a fixed absolute argv.
import subprocess  # nosec B404
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PureWindowsPath

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


def _interfaces(text: str) -> list[dict[str, str]]:
    """One dict per adapter block; each block starts at its `Name` line."""
    blocks: list[dict[str, str]] = [{}]
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        key = key.strip().lower()
        if not sep:
            continue
        if key == "name" and blocks[-1]:
            blocks.append({})
        blocks[-1].setdefault(key, value.strip())
    return blocks


def _int(raw: str | None, name: str) -> int:
    try:
        return int((raw or "").rstrip("% ").strip())
    except ValueError:
        raise ParseError(f"missing or non-numeric {name}") from None


def parse_netsh(text: str, t: float) -> Sample:
    connected = [b for b in _interfaces(text) if b.get("state", "").lower() == "connected"]
    if not connected:
        raise ParseError("no Wi-Fi interface is connected")
    f = connected[0]
    rssi = _int(f.get("rssi"), "rssi")
    if not RSSI_MIN_DBM <= rssi <= RSSI_MAX_DBM:
        raise ParseError(f"rssi {rssi} dBm outside plausible range")
    pct = _int(f.get("signal"), "signal")
    if not 0 <= pct <= 100:
        raise ParseError(f"signal {pct}% outside 0-100")
    return Sample(t=t, rssi_dbm=rssi, signal_pct=pct,
                  adapter=f.get("description", ""), band=f.get("band", ""))


def _netsh_path() -> str:
    # Absolute path: a bare "netsh" could resolve to a planted netsh.exe in the working dir.
    root = os.environ.get("SystemRoot", r"C:\Windows")
    return str(PureWindowsPath(root) / "System32" / "netsh.exe")


def _run_netsh() -> str:
    # Fixed absolute argv, no shell, no user input.
    return subprocess.run(  # nosec B603
        [_netsh_path(), "wlan", "show", "interfaces"],
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
