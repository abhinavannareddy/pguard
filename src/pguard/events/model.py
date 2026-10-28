"""Event state machine (PRD D6) with an append-only history (W5).

Claims rule: nothing is confirmed until a person confirms it, so the system actor can never
move an event to CONFIRMED or DISMISSED.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from enum import Enum


class EventKind(Enum):
    POSSIBLE_FALL = "possible_fall"
    LONG_STILLNESS = "long_stillness"
    AWAY_MOVEMENT = "away_movement"
    INTENSE_MOVEMENT = "intense_movement"
    MISSED_CHECKIN = "missed_checkin"
    NOT_WATCHING = "not_watching"


class EventState(Enum):
    CANDIDATE = "candidate"
    UNCERTAIN = "uncertain"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


_ALLOWED: dict[EventState, frozenset[EventState]] = {
    EventState.CANDIDATE: frozenset({EventState.UNCERTAIN, EventState.CONFIRMED,
                                     EventState.DISMISSED}),
    EventState.UNCERTAIN: frozenset({EventState.CANDIDATE, EventState.CONFIRMED,
                                     EventState.DISMISSED}),
    EventState.CONFIRMED: frozenset({EventState.RESOLVED}),
    EventState.DISMISSED: frozenset(),
    EventState.RESOLVED: frozenset(),
}
_PERSON_ONLY = frozenset({EventState.CONFIRMED, EventState.DISMISSED, EventState.RESOLVED})


class InvalidTransition(ValueError):
    pass


SYSTEM_ID = "pguard"


@dataclass(frozen=True)
class Actor:
    kind: str
    id: str

    def __post_init__(self) -> None:
        if self.kind not in ("person", "system"):
            raise ValueError(f"unknown actor kind {self.kind!r}")
        if self.kind == "system" and self.id != SYSTEM_ID:
            raise ValueError("the system actor has a fixed id")
        if self.kind == "person" and (not self.id.strip() or self.id.strip().lower() == SYSTEM_ID):
            raise ValueError("a person actor needs a real, non-system identity for the audit log")

    @classmethod
    def person(cls, actor_id: str) -> Actor:
        return cls("person", actor_id)

    @classmethod
    def system(cls) -> Actor:
        return cls("system", SYSTEM_ID)


@dataclass(frozen=True)
class HistoryEntry:
    t: float
    actor: Actor
    action: str
    note: str = ""


@dataclass(frozen=True)
class Event:
    id: str
    kind: EventKind
    state: EventState
    t: float
    evidence: str
    confidence: float
    rule_version: str
    history: tuple[HistoryEntry, ...]

    def transition(self, to: EventState, actor: Actor, t: float, note: str = "") -> Event:
        if to not in _ALLOWED[self.state]:
            raise InvalidTransition(f"{self.state.value} -> {to.value} is not allowed")
        if to in _PERSON_ONLY and actor.kind != "person":
            raise InvalidTransition(f"only a person may set {to.value}")
        entry = HistoryEntry(t=t, actor=actor, action=to.value, note=note)
        return replace(self, state=to, history=(*self.history, entry))


def new_event(kind: EventKind, t: float, evidence: str, confidence: float,
              rule_version: str) -> Event:
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be within 0..1")
    created = HistoryEntry(t=t, actor=Actor.system(), action="created")
    return Event(id=uuid.uuid4().hex, kind=kind, state=EventState.CANDIDATE, t=t,
                 evidence=evidence, confidence=confidence, rule_version=rule_version,
                 history=(created,))
