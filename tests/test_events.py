import pytest

from pguard.events.model import Actor, Event, EventKind, EventState, InvalidTransition, new_event
from pguard.events.wording import BANNED_TERMS, check_wording, describe


def _ev(kind: EventKind = EventKind.POSSIBLE_FALL) -> Event:
    return new_event(kind, t=100.0, evidence="burst then 90 s no movement", confidence=0.6,
                     rule_version="fall-1")


def test_new_event_starts_as_candidate_with_audit_entry():
    e = _ev()
    assert e.state is EventState.CANDIDATE
    assert (e.history[0].action, e.history[0].actor) == ("created", Actor.system())


def test_person_can_confirm_then_resolve():
    e = _ev().transition(EventState.CONFIRMED, Actor.person("monitored"), t=110)
    e = e.transition(EventState.RESOLVED, Actor.person("contact-1"), t=200)
    assert e.state is EventState.RESOLVED
    assert [h.action for h in e.history] == ["created", "confirmed", "resolved"]


def test_system_can_never_confirm():
    with pytest.raises(InvalidTransition):
        _ev().transition(EventState.CONFIRMED, Actor.system(), t=110)


def test_system_may_mark_uncertain_and_back():
    e = _ev().transition(EventState.UNCERTAIN, Actor.system(), t=101, note="quality 0.3")
    e = e.transition(EventState.CANDIDATE, Actor.system(), t=102)
    assert e.state is EventState.CANDIDATE


@pytest.mark.parametrize("terminal", [EventState.DISMISSED, EventState.RESOLVED])
def test_terminal_states_cannot_change(terminal):
    e = _ev()
    if terminal is EventState.RESOLVED:
        e = e.transition(EventState.CONFIRMED, Actor.person("p"), t=1)
    e = e.transition(terminal, Actor.person("p"), t=2)
    with pytest.raises(InvalidTransition):
        e.transition(EventState.CANDIDATE, Actor.system(), t=3)


def test_candidate_cannot_jump_to_resolved():
    with pytest.raises(InvalidTransition):
        _ev().transition(EventState.RESOLVED, Actor.person("p"), t=1)


def test_transition_returns_new_object_and_keeps_original():
    e = _ev()
    e2 = e.transition(EventState.DISMISSED, Actor.person("p"), t=5)
    assert e.state is EventState.CANDIDATE and e2 is not e


def test_confidence_must_be_probability():
    with pytest.raises(ValueError):
        new_event(EventKind.POSSIBLE_FALL, t=0, evidence="x", confidence=1.2, rule_version="v")


@pytest.mark.parametrize("kind", list(EventKind))
def test_every_event_description_passes_wording_check(kind):
    text = describe(kind, evidence="evidence here", confidence=0.5, research=True)
    assert check_wording(text, confirmed=False) == []
    assert "estimate" in text.lower()


def test_wording_check_catches_banned_terms_case_insensitively():
    found = check_wording("Possible INTRUDER and Attack detected", confirmed=False)
    assert {"intruder", "attack"} <= set(found)


def test_confirmed_word_only_allowed_when_a_person_confirmed():
    assert "confirmed" in check_wording("Fall confirmed", confirmed=False)
    assert check_wording("Fall confirmed by you", confirmed=True) == []


def test_banned_list_covers_prd_terms():
    for term in ("intruder", "attack", "assault", "suicide", "heart attack",
                 "dangerous", "suspicious"):
        assert term in BANNED_TERMS
