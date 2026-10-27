import pytest

from pguard.acquisition.windows_wifi import ParseError
from pguard.signal.replay import load_jsonl, save_jsonl
from pguard.signal.synth import generate


def test_synth_is_reproducible_and_labelled_by_seed():
    assert generate([("walking", 5)], hz=5.0, seed=1) == generate([("walking", 5)], hz=5.0, seed=1)
    assert generate([("walking", 5)], hz=5.0, seed=1) != generate([("walking", 5)], hz=5.0, seed=2)


def test_synth_unknown_scenario_raises():
    with pytest.raises(ValueError):
        generate([("flying", 5)], hz=5.0, seed=1)


def test_synth_timestamps_are_contiguous_across_segments():
    s = generate([("still", 2), ("walking", 2)], hz=5.0, seed=1)
    assert len(s) == 20 and s[0].t == 0.0 and s[-1].t == pytest.approx(3.8)


def test_replay_round_trip(tmp_path):
    s = generate([("still", 3)], hz=5.0, seed=1)
    p = tmp_path / "rec.jsonl"
    save_jsonl(s, p)
    back = load_jsonl(p)
    assert [(x.t, x.rssi_dbm) for x in back] == [(x.t, x.rssi_dbm) for x in s]


@pytest.mark.parametrize("line", ["not json", '{"t": 1}', '{"t": "a", "rssi_dbm": -40}',
                                  '{"t": 1, "rssi_dbm": "x"}'])
def test_replay_rejects_malformed_lines(tmp_path, line):
    p = tmp_path / "bad.jsonl"
    p.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(ParseError):
        load_jsonl(p)
