import json

import pytest

from pguard import cli
from pguard.acquisition.capability import classify
from pguard.acquisition.probe import ProbeReport


def _report(adapter: str | None) -> ProbeReport:
    n = 5 if adapter else 0
    return ProbeReport(
        duration_s=1, interval_s=0.1, samples=n, dropouts=0, achieved_hz=float(n),
        rssi_mean=-41.0 if n else None, rssi_stdev=0.0 if n else None,
        rssi_min=-41 if n else None, rssi_max=-41 if n else None,
        capability=classify(adapter, "Windows", False),
    )


def test_probe_command_writes_report_and_exits_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_probe", lambda **_: _report("MediaTek Wi-Fi 6E MT7922"))
    out = tmp_path / "r.json"
    assert cli.main(["probe", "--seconds", "1", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["capability"]["tier"] == "RSSI_ONLY"
    assert "tier=RSSI_ONLY" in capsys.readouterr().out


def test_probe_command_exits_2_with_blocker_when_nothing_measured(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_probe", lambda **_: _report(None))
    assert cli.main(["probe", "--out", str(tmp_path / "r.json")]) == 2
    assert "BLOCKER" in capsys.readouterr().err


def test_probe_states_command_exit_code_follows_verdict(tmp_path, monkeypatch, capsys):
    flat = {"still": [-41] * 60, "walking": [-41] * 60, "lying": [-41] * 60}
    monkeypatch.setattr(cli, "record_states", lambda *a, **k: flat)
    out = tmp_path / "s.json"
    assert cli.main(["probe-states", "--seconds", "12", "--out", str(out)]) == 3
    assert json.loads(out.read_text(encoding="utf-8"))["verdict"] == "FAIL_CONSTANT"
    assert "FAIL_CONSTANT" in capsys.readouterr().out
    moving = flat | {"walking": [-49, -41] * 30}
    monkeypatch.setattr(cli, "record_states", lambda *a, **k: moving)
    assert cli.main(["probe-states", "--seconds", "12", "--out", str(out)]) == 0


def test_unwritable_report_path_gives_clear_error_not_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_probe", lambda **_: _report("MediaTek Wi-Fi 6E MT7922"))
    bad = tmp_path / "missing-dir" / "r.json"
    assert cli.main(["probe", "--out", str(bad)]) == 1
    assert "cannot write report" in capsys.readouterr().err


@pytest.mark.parametrize("cmd", ["probe", "probe-states"])
@pytest.mark.parametrize("flag,value", [("--seconds", "0"), ("--seconds", "-5"),
                                        ("--interval", "0"), ("--seconds", "abc")])
def test_non_positive_or_bad_numbers_are_rejected_cleanly(cmd, flag, value, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([cmd, flag, value])
    assert exc.value.code == 2
    assert "must be a positive number" in capsys.readouterr().err
