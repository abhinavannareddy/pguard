import pytest

from pguard.acquisition.capability import Tier, classify
from pguard.acquisition.windows_wifi import ParseError, parse_netsh, read_sample

NETSH_OK = """
There is 1 interface on the system:

    Name                   : Wi-Fi
    Description            : MediaTek Wi-Fi 6E MT7922 160MHz Wireless LAN Card
    Physical address       : 00:00:5e:00:53:01
    State                  : connected
    SSID                   : HomeNet
    AP BSSID               : 00:00:5e:00:53:02
    Band                   : 5 GHz
    Channel                : 161
    Radio type             : 802.11ax
    Signal                 : 92%
    Rssi                   : -41
"""


def test_parse_netsh_extracts_signal_fields():
    s = parse_netsh(NETSH_OK, t=100.0)
    assert (s.t, s.rssi_dbm, s.signal_pct) == (100.0, -41, 92)
    assert s.adapter == "MediaTek Wi-Fi 6E MT7922 160MHz Wireless LAN Card"
    assert s.band == "5 GHz"


def test_parse_netsh_never_keeps_ssid_bssid_or_mac():
    dumped = repr(parse_netsh(NETSH_OK, t=1.0))
    for secret in ("HomeNet", "00:00:5e:00:53:02", "00:00:5e:00:53:01"):
        assert secret not in dumped


def test_parse_netsh_disconnected_is_error_not_zero_signal():
    with pytest.raises(ParseError):
        parse_netsh("    State                  : disconnected\n", t=1.0)


def test_parse_netsh_rejects_out_of_range_rssi():
    bad = NETSH_OK.replace("-41", "12")
    with pytest.raises(ParseError):
        parse_netsh(bad, t=1.0)


def test_read_sample_uses_injected_runner_and_clock():
    s = read_sample(runner=lambda: NETSH_OK, clock=lambda: 7.5)
    assert s.t == 7.5 and s.rssi_dbm == -41


def test_read_sample_runner_failure_becomes_parse_error():
    def boom():
        raise OSError("netsh missing")

    with pytest.raises(ParseError):
        read_sample(runner=boom, clock=lambda: 0.0)


def test_mediatek_adapter_is_tier1_without_csi_or_breathing():
    r = classify("MediaTek Wi-Fi 6E MT7922", os_name="Windows", csi_tool_present=False)
    assert r.tier is Tier.RSSI_ONLY
    assert r.csi is False
    assert r.features["breathing_rate"] is False
    assert r.features["presence_motion"] is True
    assert r.features["inactivity_watch"] is True
    assert any("CSI" in line for line in r.limitations)


def test_intel_ax210_on_windows_never_claims_csi():
    r = classify("Intel(R) Wi-Fi 6E AX210 160MHz", os_name="Windows", csi_tool_present=True)
    assert r.csi is False
    assert r.tier is Tier.RSSI_ONLY


def test_intel_ax210_on_linux_with_tool_is_csi_tier():
    r = classify("Intel(R) Wi-Fi 6E AX210 160MHz", os_name="Linux", csi_tool_present=True)
    assert r.csi is True and r.tier is Tier.CSI
    assert r.features["breathing_rate"] is True


def test_intel_ax210_on_linux_without_tool_is_not_csi():
    r = classify("Intel(R) Wi-Fi 6E AX210 160MHz", os_name="Linux", csi_tool_present=False)
    assert r.csi is False


def test_no_adapter_reports_feasibility_blocker():
    r = classify(None, os_name="Windows", csi_tool_present=False)
    assert r.tier is Tier.UNSUPPORTED
    assert r.blocker and "no usable Wi-Fi" in r.blocker
    assert not any(r.features.values())


def test_netsh_is_invoked_by_absolute_system32_path(monkeypatch):
    from pguard.acquisition import windows_wifi

    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    path = windows_wifi._netsh_path()
    assert path.lower().endswith(r"system32\netsh.exe") and ":" in path
