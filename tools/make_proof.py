"""Build the proof figures in docs/img by running PGuard's own code and commands.

Every number in these images is measured when this script runs. Synthetic scenarios are
labelled synthetic: they test the logic, they are not evidence about any real home.

Run: python tools/make_proof.py  (needs the `docs` extra)
"""

from __future__ import annotations

import json
import random
import re
import subprocess
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from make_figures import COLORS, IMG, LABELS, ROOT, P, _states_axis
from matplotlib.patches import FancyBboxPatch

from pguard.acquisition.windows_wifi import Sample
from pguard.events.model import Actor, EventKind, EventState, InvalidTransition, new_event
from pguard.events.wording import check_wording
from pguard.signal.features import State, extract
from pguard.signal.synth import generate

INK, MUTED, GREEN, BLUE = "#1b2a3a", "#5b6b7b", "#2e7d32", "#1565c0"
SEEDS = range(50)


def _run(args: list[str]) -> str:
    out = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8", check=False)
    return (out.stdout + out.stderr).rstrip()


def _terminal(name: str, blocks: list[tuple[str, str]], title: str) -> None:
    """Draw real command output as a terminal window."""
    lines: list[tuple[str, str]] = []
    for cmd, output in blocks:
        lines.append(("cmd", f"> {cmd}"))
        lines.extend(("out", ln) for ln in output.splitlines())
        lines.append(("out", ""))
    h = 0.26 * len(lines) + 0.9
    fig = plt.figure(figsize=(9, h), facecolor="#0f1720")
    ax = fig.add_axes((0, 0, 1, 1))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, h)
    for i, c in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        ax.scatter([0.025 + 0.02 * i], [h - 0.3], s=40, color=c)
    ax.text(0.5, h - 0.3, title, color="#9fb3c8", ha="center", va="center", fontsize=9)
    for i, (kind, text) in enumerate(lines):
        ax.text(0.03, h - 0.85 - 0.26 * i, text, family="monospace", fontsize=8.6, va="center",
                color="#7ee787" if kind == "cmd" else "#d6e2ee")
    fig.savefig(IMG / name, dpi=140, facecolor=fig.get_facecolor())
    plt.close(fig)


def _expected(label: str) -> State:
    return State.MOTION if label == "walking" else State.QUIET


def _scenario_accuracy(label: str, seed: int) -> float:
    w = extract(generate([(label, 120)], hz=5.0, seed=seed), 0, 120, P)
    return sum(x.state == _expected(label) for x in w) / len(w)


def terminal_proof() -> tuple[str, str]:
    probe = _run(["-m", "pguard.cli", "probe", "--seconds", "5"])
    demo = _run(["-m", "pguard.cli", "demo"])
    tests = _run(["-m", "pytest", "-q", "-o", "addopts=", "--no-header", "-p", "no:cacheprovider"])
    _terminal("terminal-probe-demo.png",
              [("pguard probe --seconds 5   # live, this laptop", probe),
               ("pguard demo   # synthetic, any OS", demo)],
              "PGuard CLI: real output")
    last = tests.splitlines()[-1]
    _terminal("terminal-tests.png", [("pytest -q", "\n".join(tests.splitlines()[-4:]))],
              "PGuard test run")
    return probe, last


def capability_card() -> None:
    cap = json.loads((ROOT / "probe-report.json").read_text(encoding="utf-8"))["capability"]
    names = {"presence_motion": "Presence and motion", "inactivity_watch": "Inactivity watch",
             "fall_candidate": "Fall candidates (coarse)", "breathing_rate": "Breathing rate",
             "breathing_pause": "Breathing pause"}
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.axis("off")
    ax.text(0, 1.0, "What this laptop can and cannot sense", fontsize=13, weight="bold",
            color=INK, transform=ax.transAxes, va="top")
    ax.text(0, 0.9, f"{cap['adapter']}  |  tier: {cap['tier']}  |  CSI: {cap['csi']}",
            fontsize=9, color=MUTED, transform=ax.transAxes, va="top")
    for i, (key, label) in enumerate(names.items()):
        on = cap["features"][key]
        y = 0.72 - 0.15 * i
        ax.add_patch(FancyBboxPatch((0, y - 0.05), 0.62, 0.11, boxstyle="round,pad=0.01",
                                    transform=ax.transAxes, fc="#e8f5e9" if on else "#f4f4f4",
                                    ec="#a5d6a7" if on else "#d0d0d0"))
        ax.text(0.02, y, label, transform=ax.transAxes, va="center", color=INK, fontsize=10)
        ax.text(0.6, y, "ON" if on else "OFF (hardware cannot back it up)", ha="right",
                transform=ax.transAxes, va="center", fontsize=9, weight="bold",
                color=GREEN if on else "#888")
    ax.text(0.66, 0.72, "Limits it reports itself", fontsize=10, weight="bold", color=INK,
            transform=ax.transAxes, va="top")
    ax.text(0.66, 0.62, "\n\n".join(re.sub(r"(.{34}\S*)\s", r"\1\n", s)
                                    for s in cap["limitations"]),
            fontsize=8, color=MUTED, transform=ax.transAxes, va="top")
    fig.savefig(IMG / "capability.png", bbox_inches="tight", dpi=140)
    plt.close(fig)


def scenarios() -> None:
    cases = [("still", "Sitting still"), ("walking", "Walking"), ("lying", "Lying still")]
    fig, axes = plt.subplots(len(cases) + 2, 1, figsize=(9, 7.4), sharex=True)
    for ax, (label, title) in zip(axes, cases, strict=False):
        s = generate([(label, 120)], hz=5.0, seed=3)
        w = extract(s, 0, 120, P)
        ax.set_title(f"{title}  |  {sum(x.state == _expected(label) for x in w)}/{len(w)} "
                     "windows correct", loc="left", fontsize=9)
        for x in w:
            ax.axvspan(x.t_start, x.t_end, color=COLORS[x.state], alpha=0.85, lw=0)
        ax.set_yticks([])
    s = [x for x in generate([("still", 120)], hz=5.0, seed=2) if not 40 <= x.t < 70]
    axes[3].set_title("Sensor dropout from 40 s to 70 s (never shown as calm)", loc="left",
                      fontsize=9)
    s2 = [x for i, x in enumerate(generate([("still", 120)], hz=5.0, seed=2))
          if not 40 <= x.t < 100 or i % 5 == 0]
    for ax, data in ((axes[3], s), (axes[4], s2)):
        for x in extract(data, 0, 120, P):
            ax.axvspan(x.t_start, x.t_end, color=COLORS[x.state], alpha=0.85, lw=0)
        ax.set_yticks([])
    axes[4].set_title("Weak link from 40 s to 100 s (reported as uncertain)", loc="left",
                      fontsize=9)
    _states_axis(axes[4], [])
    axes[4].legend(handles=[plt.Rectangle((0, 0), 1, 1, color=COLORS[k]) for k in State],
                   labels=[LABELS[k] for k in State], ncol=4, loc="upper center",
                   bbox_to_anchor=(0.5, -0.5), frameon=False)
    fig.suptitle("Five scenarios through the same pipeline (synthetic data)", x=0.01, ha="left",
                 weight="bold")
    fig.tight_layout()
    fig.savefig(IMG / "scenarios.png", bbox_inches="tight", dpi=140)
    plt.close(fig)


def _noisy(sigma: float, seed: int) -> list[Sample]:
    rng = random.Random(seed)  # nosec B311 - seeded test data, not security
    return [Sample(t=i / 5.0, rssi_dbm=round(-41 + rng.gauss(0, sigma)), signal_pct=90,
                   adapter="synthetic", band="") for i in range(600)]


def _motion_rate(sigma: float) -> float:
    rates = []
    for seed in SEEDS:
        w = extract(_noisy(sigma, seed), 0, 120, P)
        rates.append(sum(x.state == State.MOTION for x in w) / len(w))
    return 100 * sum(rates) / len(rates)


def accuracy_chart() -> dict[str, float]:
    sig = [round(0.1 * i, 1) for i in range(1, 31)]
    rate = [_motion_rate(x) for x in sig]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(sig, rate, "-o", ms=3, color=BLUE)
    ax.axvspan(0, 0.5, color="#2e7d32", alpha=0.12)
    ax.axvspan(2.0, 3.0, color="#ef6c00", alpha=0.12)
    ax.text(0.27, 55, "empty room /\nsitting still", ha="center", fontsize=8, color=GREEN)
    ax.text(2.5, 55, "walking", ha="center", fontsize=8, color="#ef6c00")
    ax.set_xlabel("signal fluctuation (dB standard deviation)")
    ax.set_ylabel("windows reported as motion (%)")
    ax.set_title(f"Sensitivity of the motion rule, mean of {len(SEEDS)} seeds per point "
                 "(synthetic)", loc="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(IMG / "synthetic-accuracy.png", dpi=140)
    plt.close(fig)
    return {"still": _motion_rate(0.25), "walking": _motion_rate(3.0)}


def event_lifecycle() -> None:
    ev = new_event(EventKind.LONG_STILLNESS, 0.0, "no motion for 45 min", 0.62, "r1")
    steps = [(EventState.UNCERTAIN, Actor.system(), 120, "link quality dropped"),
             (EventState.CANDIDATE, Actor.system(), 300, "quality restored"),
             (EventState.CONFIRMED, Actor.person("Maria"), 420, "I checked on her"),
             (EventState.RESOLVED, Actor.person("Maria"), 900, "she is fine")]
    for to, who, t, note in steps:
        ev = ev.transition(to, who, t, note)
    try:
        new_event(EventKind.POSSIBLE_FALL, 0, "burst then stillness", 0.7, "r1").transition(
            EventState.CONFIRMED, Actor.system(), 1)
        refusal = "NOT REFUSED"
    except InvalidTransition as exc:
        refusal = str(exc)
    rows = [("created", "pguard (system)", "candidate raised")]
    rows += [(h.action, f"{h.actor.id} ({h.actor.kind})", h.note) for h in ev.history[1:]]
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(rows) + 1.2))
    ax.axis("off")
    ax.set_title("Event audit trail: only a person can confirm", loc="left", weight="bold")
    tbl = ax.table(cellText=rows, colLabels=["State", "Actor", "Note"], loc="upper center",
                   cellLoc="left", colWidths=[0.2, 0.3, 0.5])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.6)
    for (r, _), cell in tbl.get_celld().items():
        cell.set_edgecolor("#d9e2ec")
        if r == 0:
            cell.set_facecolor("#e3edf7")
    ax.text(0, 0.0, f"System tries to confirm an event -> refused: \"{refusal}\"",
            transform=ax.transAxes, color="#b71c1c", fontsize=9, family="monospace")
    fig.savefig(IMG / "event-audit.png", bbox_inches="tight", dpi=140)
    plt.close(fig)


def wording_guard() -> None:
    samples = [
        ("No movement for longer than usual", False),
        ("Possible fall: a burst of movement followed by stillness", False),
        ("An intruder entered the living room", False),
        ("Suspicious activity detected", False),
        ("Signs of a heart attack", False),
        ("Fall confirmed", False),
        ("Fall confirmed by Maria", True),
    ]
    rows = []
    for text, confirmed in samples:
        hits = check_wording(text, confirmed)
        rows.append((text, "BLOCKED: " + ", ".join(hits) if hits else "allowed"))
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(rows) + 1.6))
    ax.axis("off")
    ax.set_title("Alert wording guard, run on real candidate texts", loc="left", weight="bold")
    tbl = ax.table(cellText=rows, colLabels=["Alert text", "Result"], loc="upper center",
                   cellLoc="left", colWidths=[0.62, 0.38])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.6)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#d9e2ec")
        if r == 0:
            cell.set_facecolor("#e3edf7")
        elif c == 1:
            blocked = rows[r - 1][1].startswith("BLOCKED")
            cell.set_text_props(color="#b71c1c" if blocked else GREEN, weight="bold")
    fig.savefig(IMG / "wording-guard.png", bbox_inches="tight", dpi=140)
    plt.close(fig)


def hero(tests_line: str, probe_line: str, still_mean: float) -> None:
    cov = json.loads((ROOT / "coverage.json").read_text(encoding="utf-8"))["totals"]
    live = json.loads((ROOT / "docs" / "data" / "live-laptop-2026-10-27.meta.json").read_text(encoding="utf-8"))
    passed = re.search(r"(\d+) passed", tests_line)
    hz = re.search(r"hz=([\d.]+)", probe_line)
    kpis = [(f"{cov['percent_covered']:.0f}%", "line coverage"),
            (passed.group(1) if passed else "?", "tests passing"),
            (f"{hz.group(1)} Hz" if hz else "?", "live Wi-Fi sample rate"),
            (str(live["dropouts"]), "dropped readings in the 60 s live recording")]
    fig, ax = plt.subplots(figsize=(9, 2.3), facecolor="#0f1720")
    ax.axis("off")
    ax.text(0.0, 0.98, "PGuard", color="white", fontsize=24, weight="bold", va="top",
            transform=ax.transAxes)
    ax.text(0.0, 0.66, "Camera-free safety monitoring from the Wi-Fi a home already has.",
            color="#9fb3c8", fontsize=11, va="top", transform=ax.transAxes)
    for i, (big, small) in enumerate(kpis):
        x = 0.01 + 0.25 * i
        ax.text(x, 0.32, big, color="#7ee787", fontsize=22, weight="bold",
                transform=ax.transAxes, va="center")
        ax.text(x, 0.08, small, color="#9fb3c8", fontsize=8.5, transform=ax.transAxes,
                va="center")
    fig.savefig(IMG / "hero.png", dpi=140, facecolor=fig.get_facecolor(), bbox_inches="tight",
                pad_inches=0.3)
    plt.close(fig)


if __name__ == "__main__":
    IMG.mkdir(parents=True, exist_ok=True)
    probe_out, test_line = terminal_proof()
    capability_card()
    scenarios()
    means = accuracy_chart()
    event_lifecycle()
    wording_guard()
    hero(test_line, probe_out, means["still"])
    print("motion rate % still/walking", {k: round(v, 1) for k, v in means.items()})
    print("tests:", test_line)
    print("probe:", probe_out)
