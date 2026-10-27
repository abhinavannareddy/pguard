"""Regenerate every figure in docs/img from real recordings and PGuard's own code.

Run: python tools/make_figures.py  (needs the `docs` extra; coverage.json from
`pytest --cov=pguard --cov-report=json` for the coverage figure)
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from pguard.signal.features import Params, State, extract
from pguard.signal.replay import load_jsonl
from pguard.signal.synth import generate

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "img"
LIVE = ROOT / "docs" / "data" / "live-laptop-2026-10-27.jsonl"
COLORS = {State.QUIET: "#2e7d32", State.MOTION: "#ef6c00",
          State.UNCERTAIN: "#9e9e9e", State.NO_DATA: "#c62828"}
LABELS = {State.QUIET: "No motion (measured)", State.MOTION: "Motion",
          State.UNCERTAIN: "Uncertain (abstain)", State.NO_DATA: "No data"}
P = Params(window_s=2.0, expected_hz=5.0, stale_s=1.0)

plt.rcParams.update({"figure.dpi": 140, "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False})


def _states_axis(ax, windows) -> None:
    for w in windows:
        ax.axvspan(w.t_start, w.t_end, color=COLORS[w.state], alpha=0.85, lw=0)
    ax.set_yticks([])
    ax.set_xlabel("time (s)")
    ax.legend(handles=[Patch(color=COLORS[s], label=LABELS[s]) for s in State],
              ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.45), frameon=False)


def live_baseline() -> None:
    s = load_jsonl(LIVE)
    fig, ax = plt.subplots(figsize=(9, 3))
    ax.plot([x.t for x in s], [x.rssi_dbm for x in s], ".", ms=4, color="#1565c0")
    ax.set_ylim(-60, -30)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("RSSI (dBm)")
    hz = len(s) / (s[-1].t - s[0].t)
    ax.set_title(f"Live recording on the hub laptop: static room, {len(s)} samples, "
                 f"{hz:.2f} Hz, 0 dropouts", loc="left")
    fig.tight_layout()
    fig.savefig(IMG / "live-baseline.png")
    plt.close(fig)


def pipeline() -> None:
    s = generate([("still", 40), ("walking", 40), ("still", 40)], hz=5.0, seed=1)
    w = extract(s, 0, 120, P)
    fig, (a, b) = plt.subplots(2, 1, figsize=(9, 4.4), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})
    a.plot([x.t for x in s], [x.rssi_dbm for x in s], lw=0.8, color="#1565c0")
    a.set_ylabel("RSSI (dBm)")
    a.set_title("Signal to decision: still, walking, still (synthetic data)", loc="left")
    _states_axis(b, w)
    fig.tight_layout()
    fig.savefig(IMG / "pipeline.png", bbox_inches="tight")
    plt.close(fig)


def fault_injection() -> None:
    s = generate([("still", 120)], hz=5.0, seed=2)
    s = [x for x in s if not 40 <= x.t < 70]                        # sensor dropout
    s = [x for i, x in enumerate(s) if not (80 <= x.t < 100) or i % 5 == 0]  # weak link
    w = extract(s, 0, 120, P)
    fig, (a, b) = plt.subplots(2, 1, figsize=(9, 4.4), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})
    a.plot([x.t for x in s], [x.rssi_dbm for x in s], ".", ms=3, color="#1565c0")
    a.axvspan(40, 70, color=COLORS[State.NO_DATA], alpha=0.12)
    a.axvspan(80, 100, color=COLORS[State.UNCERTAIN], alpha=0.2)
    a.text(55, a.get_ylim()[1], "sensor dropout", ha="center", va="top")
    a.text(90, a.get_ylim()[1], "weak link", ha="center", va="top")
    a.set_ylabel("RSSI (dBm)")
    a.set_title("Safety rule S4: a gap is never shown as calm (synthetic fault injection)",
                loc="left")
    _states_axis(b, w)
    fig.tight_layout()
    fig.savefig(IMG / "fault-injection.png", bbox_inches="tight")
    plt.close(fig)


def coverage() -> None:
    files = json.loads((ROOT / "coverage.json").read_text(encoding="utf-8"))["files"]
    rows = sorted(
        ((Path(f).with_suffix("").as_posix().split("pguard/", 1)[-1],
          d["summary"]["percent_covered"]) for f, d in files.items()
         if d["summary"]["num_statements"]),
        key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(9, 0.32 * len(rows) + 1))
    ax.barh([r[0] for r in rows], [r[1] for r in rows], color="#2e7d32")
    for i, (_, pct) in enumerate(rows):
        ax.text(pct - 1, i, f"{pct:.0f}%", va="center", ha="right", color="white", fontsize=8)
    ax.set_xlim(0, 100)
    ax.set_xlabel("line coverage (%)")
    ax.set_title("Test coverage by module (measured by pytest-cov)", loc="left")
    fig.tight_layout()
    fig.savefig(IMG / "coverage.png")
    plt.close(fig)


if __name__ == "__main__":
    IMG.mkdir(parents=True, exist_ok=True)
    for make in (live_baseline, pipeline, fault_injection, coverage):
        make()
        print(f"wrote {make.__name__}")
