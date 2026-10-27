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
