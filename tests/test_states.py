import json

import pytest

from pguard.acquisition.states import Verdict, analyze_states, record_states
from pguard.acquisition.windows_wifi import ParseError, Sample


def _noisy(base: int, amp: int, n: int = 60) -> list[int]:
    return [base + (amp if i % 2 else -amp) for i in range(n)]


def test_constant_signal_everywhere_fails_as_insensitive():
    r = analyze_states({"still": [-41] * 60, "walking": [-41] * 60, "lying": [-41] * 60},
                       hz=5.0)
    assert r.verdict is Verdict.FAIL_CONSTANT
    assert "cannot" in r.message.lower()


def test_walking_with_clear_variance_passes():
    r = analyze_states({"still": [-41] * 60, "walking": _noisy(-45, 4), "lying": [-41] * 60},
                       hz=5.0)
    assert r.verdict is Verdict.PASS
    assert ("still", "walking") in r.separable_pairs


def test_mean_shift_alone_separates_lying_from_still():
    r = analyze_states({"still": [-41] * 60, "walking": _noisy(-45, 4), "lying": [-44] * 60},
                       hz=5.0)
    assert ("still", "lying") in r.separable_pairs


def test_variation_without_state_difference_is_indistinguishable():
    same = _noisy(-41, 1)
    r = analyze_states({"still": same, "walking": list(same), "lying": list(same)}, hz=5.0)
    assert r.verdict is Verdict.FAIL_INDISTINGUISHABLE


def test_too_few_samples_is_inconclusive_not_pass():
    r = analyze_states({"still": [-41] * 3, "walking": _noisy(-45, 4, 3), "lying": [-41] * 3},
                       hz=5.0)
    assert r.verdict is Verdict.INCONCLUSIVE


def test_missing_label_raises():
    with pytest.raises(ValueError):
        analyze_states({"still": [-41] * 60}, hz=5.0)


def test_record_states_collects_per_label_and_announces_each():
    t = {"now": 0.0}
    announced: list[str] = []

    def sleep(s: float) -> None:
        t["now"] += s

    def read() -> Sample:
        return Sample(t=t["now"], rssi_dbm=-41, signal_pct=90, adapter="x", band="5 GHz")

    out = record_states(
        labels=("still", "walking"), seconds=2.0, interval_s=0.5, countdown_s=1.0,
        read=read, clock=lambda: t["now"], sleep=sleep, announce=announced.append,
    )
    assert set(out) == {"still", "walking"}
    assert len(out["still"]) == 4 and len(announced) >= 2


def test_record_states_skips_dropouts():
    t = {"now": 0.0}
    calls = iter(range(100))

    def read() -> Sample:
        if next(calls) % 2:
            raise ParseError("x")
        return Sample(t=t["now"], rssi_dbm=-41, signal_pct=90, adapter="x", band="")

    out = record_states(
        labels=("still",), seconds=2.0, interval_s=0.5, countdown_s=0.0, read=read,
        clock=lambda: t["now"], sleep=lambda s: t.__setitem__("now", t["now"] + s),
        announce=lambda _m: None,
    )
    assert len(out["still"]) == 2


def test_report_serialises_without_identifiers():
    r = analyze_states({"still": [-41] * 60, "walking": _noisy(-45, 4), "lying": [-41] * 60},
                       hz=5.0)
    blob = json.dumps(r.to_dict())
    assert json.loads(blob)["verdict"] == "PASS"
