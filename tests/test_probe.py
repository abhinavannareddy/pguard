import json

import pytest

from pguard.acquisition.capability import Tier
from pguard.acquisition.probe import run_probe
from pguard.acquisition.windows_wifi import ParseError, Sample


def _sample(t: float, rssi: int) -> Sample:
    return Sample(t=t, rssi_dbm=rssi, signal_pct=90, adapter="MediaTek Wi-Fi 6E MT7922", band="5 GHz")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, s: float) -> None:
        self.now += s


def test_probe_measures_rate_and_signal_stats():
    clock = FakeClock()
    rssis = iter([-40, -42, -44, -42] * 100)
    report = run_probe(
        duration_s=10, interval_s=0.5,
        read=lambda: _sample(clock(), next(rssis)),
        clock=clock, sleep=clock.sleep, os_name="Windows", csi_tool_present=False,
    )
    assert report.samples == 20
    assert report.achieved_hz == pytest.approx(2.0, rel=0.05)
    assert report.rssi_mean == pytest.approx(-42.0)
    assert (report.rssi_min, report.rssi_max) == (-44, -40)
    assert report.dropouts == 0
    assert report.capability.tier is Tier.RSSI_ONLY


def test_probe_counts_dropouts_instead_of_inventing_samples():
    clock = FakeClock()
    calls = iter(range(100))

    def read() -> Sample:
        if next(calls) % 2:
            raise ParseError("not connected")
        return _sample(clock(), -50)

    report = run_probe(duration_s=4, interval_s=1.0, read=read, clock=clock, sleep=clock.sleep,
                       os_name="Windows", csi_tool_present=False)
    assert report.samples == 2 and report.dropouts == 2


def test_probe_with_no_samples_reports_blocker_and_no_stats():
    clock = FakeClock()

    def read() -> Sample:
        raise ParseError("not connected")

    report = run_probe(duration_s=3, interval_s=1.0, read=read, clock=clock, sleep=clock.sleep,
                       os_name="Windows", csi_tool_present=False)
    assert report.samples == 0 and report.rssi_mean is None
    assert report.capability.tier is Tier.UNSUPPORTED
    assert report.capability.blocker


def test_probe_rejects_non_positive_duration_or_interval():
    with pytest.raises(ValueError):
        run_probe(duration_s=0, interval_s=1.0, read=lambda: None, os_name="Windows",
                  csi_tool_present=False)
    with pytest.raises(ValueError):
        run_probe(duration_s=5, interval_s=0, read=lambda: None, os_name="Windows",
                  csi_tool_present=False)


def test_report_json_has_no_network_identifiers():
    clock = FakeClock()
    report = run_probe(duration_s=2, interval_s=1.0, read=lambda: _sample(clock(), -41),
                       clock=clock, sleep=clock.sleep, os_name="Windows", csi_tool_present=False)
    blob = json.dumps(report.to_dict())
    assert "ssid" not in blob.lower() and "bssid" not in blob.lower()
    assert json.loads(blob)["capability"]["tier"] == "RSSI_ONLY"
