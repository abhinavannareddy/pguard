import random

import pytest

from pguard.acquisition.windows_wifi import Sample
from pguard.signal.features import Params, State, extract
from pguard.signal.synth import generate

P = Params(window_s=2.0, expected_hz=5.0, stale_s=1.0)


def _drop_between(samples: list[Sample], a: float, b: float) -> list[Sample]:
    return [s for s in samples if not a <= s.t < b]


def _replace_rssi(s: Sample, rssi: int) -> Sample:
    return Sample(t=s.t, rssi_dbm=rssi, signal_pct=s.signal_pct, adapter=s.adapter, band=s.band)


def test_still_scenario_is_quiet_with_high_quality():
    s = generate([("still", 60)], hz=5.0, seed=1)
    w = extract(s, 0, 60, P)
    assert all(x.state is State.QUIET for x in w)
    assert all(x.quality >= 0.9 for x in w)


def test_walking_scenario_is_motion():
    s = generate([("walking", 60)], hz=5.0, seed=1)
    w = extract(s, 0, 60, P)
    assert sum(x.state is State.MOTION for x in w) / len(w) >= 0.9


def test_dropped_segment_is_no_data_never_quiet():
    s = _drop_between(generate([("still", 60)], hz=5.0, seed=2), 20, 40)
    w = extract(s, 0, 60, P)
    gap = [x for x in w if 20 <= x.t_start < 40]
    assert gap and all(x.state is State.NO_DATA for x in gap)


def test_low_coverage_is_uncertain_with_flag():
    s = generate([("still", 60)], hz=5.0, seed=3)[::5]  # coverage 0.4
    w = extract(s, 0, 60, P)
    assert all(x.state is State.UNCERTAIN for x in w)
    assert all("low_coverage" in x.flags for x in w)


def test_all_corrupt_window_is_no_data():
    s = [_replace_rssi(x, 12) for x in generate([("still", 10)], hz=5.0, seed=4)]
    w = extract(s, 0, 10, P)
    assert all(x.state is State.NO_DATA and "corrupt_samples" in x.flags for x in w)


def test_partly_corrupt_window_lowers_quality_and_flags():
    s = generate([("still", 10)], hz=5.0, seed=5)
    s = [_replace_rssi(x, 99) if i % 5 == 0 else x for i, x in enumerate(s)]
    w = extract(s, 0, 10, P)
    assert all("corrupt_samples" in x.flags and x.quality < 0.9 for x in w)


def test_stale_sensor_in_window_is_uncertain_not_quiet():
    s = [x for x in generate([("still", 10)], hz=5.0, seed=6) if x.t < 5.0]
    w = extract(s, 0, 10, Params(window_s=10.0, expected_hz=5.0, stale_s=1.0))
    assert w[0].state is State.UNCERTAIN and "stale" in w[0].flags


def test_out_of_order_input_gives_same_result():
    s = generate([("still", 20), ("walking", 20)], hz=5.0, seed=7)
    shuffled = random.Random(0).sample(s, len(s))
    assert extract(shuffled, 0, 40, P) == extract(s, 0, 40, P)


def test_extraction_is_reproducible():
    s = generate([("walking", 20)], hz=5.0, seed=8)
    assert extract(s, 0, 20, P) == extract(s, 0, 20, P)


def test_fault_injection_never_yields_confident_state_on_poor_data():
    rng = random.Random(42)
    base = generate([("still", 60), ("walking", 60)], hz=5.0, seed=9)
    for _ in range(50):
        keep = rng.uniform(0.0, 1.0)
        faulty = [x for x in base if rng.random() < keep]
        for w in extract(faulty, 0, 120, P):
            if w.quality < P.min_quality:
                assert w.state in (State.NO_DATA, State.UNCERTAIN)


def test_params_are_validated():
    with pytest.raises(ValueError):
        Params(window_s=0)
    with pytest.raises(ValueError):
        Params(min_quality=1.5)


def test_params_version_is_recorded_on_every_window():
    s = generate([("still", 4)], hz=5.0, seed=10)
    assert {x.params_version for x in extract(s, 0, 4, P)} == {P.version}
