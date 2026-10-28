"""Regression tests for defects found in the full recheck."""

import pytest

import pguard
from pguard.acquisition.states import Verdict, analyze_states
from pguard.acquisition.windows_wifi import ParseError, parse_netsh
from pguard.signal.features import Params
from pguard.signal.replay import load_jsonl


def test_all_dropouts_is_inconclusive_not_a_verdict_about_the_signal():
    r = analyze_states({"still": [], "walking": [], "lying": []}, hz=0.0)
    assert r.verdict is Verdict.INCONCLUSIVE


def test_low_rate_with_few_samples_does_not_crash():
    r = analyze_states({"still": [-41], "walking": [-45], "lying": [-43]}, hz=0.3)
    assert r.verdict is Verdict.INCONCLUSIVE


@pytest.mark.parametrize("t", ["NaN", "Infinity", "-Infinity"])
def test_replay_rejects_non_finite_timestamps(tmp_path, t):
    p = tmp_path / "r.jsonl"
    p.write_text(f'{{"t": {t}, "rssi_dbm": -40}}\n', encoding="utf-8")
    with pytest.raises(ParseError):
        load_jsonl(p)


def test_replay_rejects_non_numeric_signal_pct_as_parse_error(tmp_path):
    p = tmp_path / "r.jsonl"
    p.write_text('{"t": 1, "rssi_dbm": -40, "signal_pct": "x"}\n', encoding="utf-8")
    with pytest.raises(ParseError):
        load_jsonl(p)


TWO_ADAPTERS = """
There are 2 interfaces on the system:

    Name                   : Wi-Fi 2
    Description            : USB Dongle
    State                  : disconnected

    Name                   : Wi-Fi
    Description            : MediaTek Wi-Fi 6E MT7922
    State                  : connected
    SSID                   : HomeNet
    Signal                 : 80%
    Rssi                   : -55
"""


def test_netsh_uses_the_connected_adapter_when_several_exist():
    s = parse_netsh(TWO_ADAPTERS, t=1.0)
    assert (s.adapter, s.rssi_dbm) == ("MediaTek Wi-Fi 6E MT7922", -55)


def test_params_version_has_one_source_of_truth():
    assert Params().version == pguard.PARAMS_VERSION


# ---- code-review round 2 ----
import subprocess

from pguard import cli
from pguard.acquisition import windows_wifi
from pguard.events.model import Actor, EventKind, EventState, InvalidTransition, new_event
from pguard.events.wording import check_wording
from pguard.signal.features import extract
from pguard.signal.synth import generate


@pytest.mark.parametrize("text,term", [
    ("Two intruders detected", "intruder"), ("possible attacks", "attack"),
    ("burglars nearby", "burglar"), ("weapons seen", "weapon"),
    ("was assaulted", "assault"), ("signs of strokes", "stroke"),
    ("several break-ins", "break-in"), ("diagnoses made", "diagnosis"),
])
def test_wording_check_catches_plurals_and_word_forms(text, term):
    assert term in check_wording(text, confirmed=False)


def test_wording_does_not_flag_innocent_lookalikes():
    assert check_wording("Keystrokes and a backstroke are fine", confirmed=False) == []


def test_replay_huge_integer_timestamp_is_parse_error(tmp_path):
    p = tmp_path / "r.jsonl"
    p.write_text('{"t": 1' + "0" * 400 + ', "rssi_dbm": -40}\n', encoding="utf-8")
    with pytest.raises(ParseError):
        load_jsonl(p)


def test_replay_absurdly_long_integer_is_parse_error(tmp_path):
    p = tmp_path / "r.jsonl"
    p.write_text('{"t": 1' + "0" * 5000 + ', "rssi_dbm": -40}\n', encoding="utf-8")
    with pytest.raises(ParseError):
        load_jsonl(p)


@pytest.mark.parametrize("pct", ["5000", "-3", "101"])
def test_replay_rejects_out_of_range_signal_pct(tmp_path, pct):
    p = tmp_path / "r.jsonl"
    p.write_text(f'{{"t": 1, "rssi_dbm": -40, "signal_pct": {pct}}}\n', encoding="utf-8")
    with pytest.raises(ParseError):
        load_jsonl(p)


def test_replay_accepts_whole_number_float_signal_pct(tmp_path):
    p = tmp_path / "r.jsonl"
    p.write_text('{"t": 1, "rssi_dbm": -40, "signal_pct": 80.0}\n', encoding="utf-8")
    assert load_jsonl(p)[0].signal_pct == 80


def test_countdown_zero_is_allowed_but_negative_is_not(monkeypatch, tmp_path):
    flat = {"still": [-41] * 60, "walking": [-41] * 60, "lying": [-41] * 60}
    monkeypatch.setattr(cli, "record_states", lambda *a, **k: flat)
    out = str(tmp_path / "s.json")
    assert cli.main(["probe-states", "--countdown", "0", "--seconds", "12", "--out", out]) == 3
    with pytest.raises(SystemExit) as exc:
        cli.main(["probe-states", "--countdown", "-1"])
    assert exc.value.code == 2


def test_bad_output_path_is_rejected_before_recording(tmp_path, monkeypatch, capsys):
    called = []
    monkeypatch.setattr(cli, "record_states", lambda *a, **k: called.append(1) or {})
    monkeypatch.setattr(cli, "run_probe", lambda **k: called.append(1))
    bad = str(tmp_path / "nope" / "r.json")
    assert cli.main(["probe-states", "--out", bad]) == 1
    assert cli.main(["probe", "--out", bad]) == 1
    assert called == []
    assert "cannot write report" in capsys.readouterr().err


def test_demo_command_shows_all_four_states(capsys):
    assert cli.main(["demo", "--seconds", "30"]) == 0
    out = capsys.readouterr().out
    assert "synthetic" in out.lower()
    for word in ("quiet", "motion", "uncertain", "no_data"):
        assert word in out


def test_low_coverage_flag_tracks_min_quality_by_design():
    p = Params(window_s=2.0, expected_hz=5.0, stale_s=1.0, min_quality=0.9)
    s = generate([("still", 20)], hz=5.0, seed=3)[::4]  # coverage 0.5..
    for w in extract(s, 0, 20, p):
        assert ("low_coverage" in w.flags) == (w.n_valid / 10 < 0.9)


def test_person_actor_needs_a_real_identity():
    with pytest.raises(ValueError):
        Actor.person("")
    with pytest.raises(ValueError):
        Actor.person("pguard")
    with pytest.raises(ValueError):
        Actor("person", "   ")
    with pytest.raises(ValueError):
        Actor("robot", "x")
    with pytest.raises(ValueError):
        Actor("system", "someone")


def test_forged_person_actor_cannot_confirm():
    e = new_event(EventKind.POSSIBLE_FALL, t=0, evidence="x", confidence=0.5, rule_version="v")
    with pytest.raises((InvalidTransition, ValueError)):
        e.transition(EventState.CONFIRMED, Actor("person", "pguard"), t=1)


def test_run_netsh_really_uses_absolute_system32_path(monkeypatch):
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, stdout="x", stderr="")

    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    monkeypatch.setattr(windows_wifi.subprocess, "run", fake_run)
    windows_wifi._run_netsh()
    assert seen["argv"][0].lower().endswith(r"system32\netsh.exe")
    assert seen["argv"][0] != "netsh" and seen["argv"][1:] == ["wlan", "show", "interfaces"]
