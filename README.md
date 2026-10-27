# PGuard

Privacy-first Wi-Fi safety and wellbeing monitor. Camera-free: it watches how the home Wi-Fi
signal changes, reports what it measured, how sure it is, and what it cannot know.
It is **not** a medical device, emergency service or certified alarm system.

## Status

Phase 0 (feasibility) in progress. Nothing below is claimed beyond what was measured.

## Quick start (Windows)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest --cov=pguard
.venv\Scripts\python -m pguard.cli probe --seconds 15 --out probe-report.json
```

## Probe report (measured, 2026-10-27)

Hardware: MediaTek Wi-Fi 6E MT7922 card, Windows 11, 5 GHz, one room, nobody moving.

| Source | Samples | Rate | RSSI values seen |
|---|---|---|---|
| `netsh wlan show interfaces` (15 s) | 76 | ~5 Hz | -41 dBm only |
| Native Wi-Fi API `WlanQueryInterface` RSSI (10 s) | 194 | ~19 Hz | -41 dBm only |

Result: **Tier 1 (RSSI only).** This card is not an Intel AX200/AX210, and Windows exposes no
CSI, so breathing and breathing-pause detection are unavailable on this laptop.

**Open finding:** the reported RSSI did not vary at all in a static scene. Whether it changes
when a person walks, sits or lies still has not been measured yet. Until that labeled-state
test passes, presence/motion/inactivity are *unproven* on this hardware (PRD Phase 0 exit gate).

## Scope of v1

In: Tier 1 sensing, movement timeline, inactivity, fall candidate (research label), check-in,
escalation, email and Telegram/ntfy alerts, heartbeat, modes, duress code, audit log, dashboard.
Deferred (see `docs/adr`): radar nodes, CSI/breathing, wellbeing layer, Go/Rust/mobile, Kubernetes.

## Known inconsistencies to resolve

- `Dockerfile` references `probe.py`, `cpp/` and `models/`, which do not exist yet.
- `web/app/page.tsx` imports modules under `web/lib` and `web/components` not yet written.
