"""Parity tests: the C++20 core must agree with the Python reference implementation."""

import os

import pytest

from pguard.native import NativeUnavailable, Ring, extract_native, load
from pguard.signal.features import Params, State, extract
from pguard.signal.synth import generate

P = Params(window_s=2.0, expected_hz=5.0, stale_s=1.0)

try:
    load()
    AVAILABLE = True
except NativeUnavailable:
    AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not AVAILABLE and not os.environ.get("PGUARD_REQUIRE_NATIVE"),
    reason="native core not built (cmake -S cpp -B cpp/build && cmake --build cpp/build)",
)


def _assert_same(py, nat):
    assert len(py) == len(nat)
    for a, b in zip(py, nat, strict=True):
        assert (a.state, a.flags, a.n_valid, a.n_corrupt) == (b.state, b.flags, b.n_valid, b.n_corrupt)
        assert a.quality == pytest.approx(b.quality, abs=1e-3)
        for x, y in ((a.mean_dbm, b.mean_dbm), (a.motion_energy, b.motion_energy)):
            assert (x is None) == (y is None)
            if x is not None:
                assert x == pytest.approx(y, abs=1e-3)


def test_native_is_required_when_flagged():
    if os.environ.get("PGUARD_REQUIRE_NATIVE"):
        assert AVAILABLE, "PGUARD_REQUIRE_NATIVE is set but the native core is not built"


def test_parity_on_still_then_walking_then_still():
    s = generate([("still", 40), ("walking", 40), ("still", 40)], hz=5.0, seed=1)
    _assert_same(extract(s, 0, 120, P), extract_native(s, 0, 120, P))


def test_parity_with_dropout_and_weak_link():
    s = generate([("still", 120)], hz=5.0, seed=2)
    s = [x for x in s if not 40 <= x.t < 70]
    s = [x for i, x in enumerate(s) if not (80 <= x.t < 100) or i % 5 == 0]
    py, nat = extract(s, 0, 120, P), extract_native(s, 0, 120, P)
    _assert_same(py, nat)
    assert State.NO_DATA in {w.state for w in nat} and State.UNCERTAIN in {w.state for w in nat}


def test_parity_with_corrupt_samples_and_shuffled_order():
    import random
    from dataclasses import replace

    s = generate([("walking", 30)], hz=5.0, seed=3)
    s = [replace(x, rssi_dbm=99) if i % 7 == 0 else x for i, x in enumerate(s)]
    random.Random(1).shuffle(s)
    _assert_same(extract(s, 0, 30, P), extract_native(s, 0, 30, P))


@pytest.mark.parametrize("seed", range(10))
def test_parity_random_fault_injection(seed):
    import random

    rng = random.Random(seed)
    base = generate([("still", 60), ("walking", 60)], hz=5.0, seed=seed)
    faulty = [x for x in base if rng.random() < rng.uniform(0.0, 1.0)]
    _assert_same(extract(faulty, 0, 120, P), extract_native(faulty, 0, 120, P))


def test_native_rejects_invalid_params():
    bad = Params()
    object.__setattr__(bad, "motion_threshold_db", -1.0)  # bypass Python validation on purpose
    with pytest.raises(ValueError):
        extract_native([], 0, 10, bad)


def test_ring_buffer_counts_dropped_samples_instead_of_hiding_them():
    r = Ring(capacity=4)
    for i in range(6):
        r.push(float(i), -40 - i)
    assert r.dropped == 2
    t, rssi = r.drain()
    assert t == [2.0, 3.0, 4.0, 5.0] and rssi == [-42, -43, -44, -45]
    assert r.drain() == ([], [])
    r.close()
