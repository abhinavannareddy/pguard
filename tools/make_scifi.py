"""Sci-fi style demo images. These are ILLUSTRATIONS driven by PGuard's synthetic pipeline,
not measurements of any home. Each image says so in its caption line.

Run: python tools/make_scifi.py  (needs the `docs` extra)
"""

from __future__ import annotations

import numpy as np
from make_figures import COLORS, IMG, P
from matplotlib import pyplot as plt

from pguard.signal.features import State, extract
from pguard.signal.synth import generate

BG, CYAN, MAGENTA, AMBER, DIM = "#050a14", "#00e5ff", "#ff2bd6", "#ffb300", "#5b7088"
NOTE = "ILLUSTRATION from synthetic data, not a measurement of any home"


def _frame(w: float, h: float):
    fig = plt.figure(figsize=(w, h), facecolor=BG)
    ax = fig.add_axes((0, 0, 1, 1), facecolor=BG)
    ax.axis("off")
    return fig, ax


def _grid(ax, xlim, ylim) -> None:
    for x in np.linspace(*xlim, 25):
        ax.plot([x, x], ylim, color=CYAN, alpha=0.05, lw=0.6)
    for y in np.linspace(*ylim, 12):
        ax.plot(xlim, [y, y], color=CYAN, alpha=0.05, lw=0.6)


def signal_field() -> None:
    """Wi-Fi ripples from a router; a walking figure distorts the field."""
    fig, ax = _frame(9, 5)
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 10)
    _grid(ax, (0, 18), (0, 10))
    rng = np.random.default_rng(7)
    rx, ry, px, py = 3.0, 5.0, 12.5, 5.0
    th = np.linspace(-np.pi / 2.2, np.pi / 2.2, 400)
    for i, r in enumerate(np.linspace(1.0, 14, 16)):
        a = 0.75 * (1 - i / 17)
        ax.plot(rx + r * np.cos(th), ry + r * np.sin(th), color=CYAN, alpha=a, lw=1.4)
    for r in np.linspace(0.6, 3.2, 6):  # distortion around the person
        t = np.linspace(0, 2 * np.pi, 200)
        wob = 1 + 0.12 * np.sin(6 * t + r)
        ax.plot(px + r * wob * np.cos(t), py + r * wob * np.sin(t) * 0.8, color=MAGENTA,
                alpha=0.8 - r / 5, lw=1.2)
    ax.scatter([rx], [ry], s=260, color=CYAN, zorder=5)
    ax.scatter([rx], [ry], s=900, facecolors="none", edgecolors=CYAN, zorder=5)
    ax.scatter([px], [py], s=120, color=MAGENTA, zorder=5)
    ax.scatter(rng.uniform(0, 18, 60), rng.uniform(0, 10, 60), s=2, color="white", alpha=0.4)
    ax.text(rx, ry - 1.2, "ROUTER", color=CYAN, ha="center", fontsize=8, family="monospace")
    ax.text(px, py - 1.2, "MOTION DISTURBS SIGNAL", color=MAGENTA, ha="center", fontsize=8,
            family="monospace")
    ax.text(0.4, 9.4, "PGUARD // SIGNAL FIELD", color="white", fontsize=16, weight="bold",
            family="monospace")
    ax.text(0.4, 8.7, "no camera. no microphone. only the Wi-Fi already in the room.",
            color=DIM, fontsize=9, family="monospace")
    ax.text(0.4, 0.3, NOTE, color=DIM, fontsize=7, family="monospace")
    fig.savefig(IMG / "scifi-signal-field.png", dpi=150, facecolor=BG)
    plt.close(fig)


def radar() -> None:
    """Polar sweep whose blips come from real windowed states on synthetic data."""
    s = generate([("still", 40), ("walking", 40), ("still", 20), ("walking", 20)], hz=5.0,
                 seed=11)
    w = extract(s, 0, 120, P)
    fig = plt.figure(figsize=(7, 7), facecolor=BG)
    ax = fig.add_axes((0.06, 0.06, 0.88, 0.84), projection="polar", facecolor=BG)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 10)
    ax.set_yticklabels([])
    ax.set_xticklabels([])
    ax.grid(color=CYAN, alpha=0.25)
    ax.spines["polar"].set_color(CYAN)
    for r in (2.5, 5, 7.5, 10):
        ax.plot(np.linspace(0, 2 * np.pi, 200), [r] * 200, color=CYAN, alpha=0.18, lw=0.8)
    sweep = np.linspace(-0.9, 0, 60)
    for i, a in enumerate(sweep):
        ax.plot([a + 4.2, a + 4.2], [0, 10], color=CYAN, alpha=0.015 + 0.012 * i, lw=3)
    for k, x in enumerate(w):
        ang = 2 * np.pi * k / len(w)
        energy = x.motion_energy or 0.0
        ax.scatter([ang], [2 + min(energy, 6) * 1.2 + 0.3], s=20 + 40 * min(energy, 4),
                   color=COLORS[x.state] if x.state != State.QUIET else CYAN,
                   alpha=0.9 if x.state == State.MOTION else 0.5)
    fig.text(0.5, 0.95, "PGUARD // MOTION RADAR", color="white", ha="center", fontsize=15,
             weight="bold", family="monospace")
    fig.text(0.5, 0.02, "each dot = one 2 s window, radius = motion energy | " + NOTE,
             color=DIM, ha="center", fontsize=6.5, family="monospace")
    fig.savefig(IMG / "scifi-radar.png", dpi=150, facecolor=BG)
    plt.close(fig)


def hud() -> None:
    """Heads-up display: live-style trace plus a state ribbon and status readouts."""
    s = generate([("still", 35), ("walking", 30), ("still", 55)], hz=5.0, seed=4)
    w = extract(s, 0, 120, P)
    fig, ax = _frame(10, 5.6)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.6)
    ax.text(0.3, 5.2, "PGUARD // COMMAND VIEW", color="white", fontsize=16, weight="bold",
            family="monospace")
    ax.text(9.7, 5.2, "● SENSING", color="#39ff14", ha="right", fontsize=10,
            family="monospace")
    tr = fig.add_axes((0.05, 0.38, 0.9, 0.42), facecolor="#08111f")
    tr.plot([x.t for x in s], [x.rssi_dbm for x in s], color=CYAN, lw=0.9)
    tr.fill_between([x.t for x in s], [x.rssi_dbm for x in s], -60, color=CYAN, alpha=0.1)
    tr.set_ylim(-52, -33)
    tr.tick_params(colors=DIM, labelsize=7)
    for sp in tr.spines.values():
        sp.set_color(DIM)
    tr.set_ylabel("RSSI dBm", color=DIM, fontsize=7)
    rb = fig.add_axes((0.05, 0.27, 0.9, 0.07), facecolor=BG)
    for x in w:
        rb.axvspan(x.t_start, x.t_end, color=COLORS[x.state], alpha=0.9, lw=0)
    rb.set_xlim(0, 120)
    rb.axis("off")
    moving = sum(x.state == State.MOTION for x in w) * P.window_s
    cards = [("STATE NOW", w[-1].state.value.upper().replace("_", " ")),
             ("MOTION TIME", f"{moving:.0f} s of 120 s"),
             ("WINDOWS", f"{len(w)} scored"),
             ("QUALITY", f"{np.mean([x.quality for x in w]):.2f} mean")]
    for i, (k, v) in enumerate(cards):
        x0 = 0.3 + 2.4 * i
        ax.add_patch(plt.Rectangle((x0, 0.35), 2.2, 1.1, fc="#08111f", ec=CYAN, lw=0.8))
        ax.text(x0 + 0.15, 1.2, k, color=DIM, fontsize=7, family="monospace")
        ax.text(x0 + 0.15, 0.65, v, color=AMBER, fontsize=12, weight="bold", family="monospace")
    ax.text(0.3, 0.12, NOTE, color=DIM, fontsize=7, family="monospace")
    fig.savefig(IMG / "scifi-hud.png", dpi=150, facecolor=BG)
    plt.close(fig)


if __name__ == "__main__":
    IMG.mkdir(parents=True, exist_ok=True)
    for make in (signal_field, radar, hud):
        make()
        print(f"wrote {make.__name__}")
