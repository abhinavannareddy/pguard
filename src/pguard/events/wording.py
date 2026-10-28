"""Alert wording and the automated banned-terms check (PRD claims policy, I4, wording target).

Alerts state plain observations. They never accuse, diagnose or predict, and never say
"confirmed" unless a person confirmed the event.
"""

from __future__ import annotations

import re

from .model import EventKind

BANNED_TERMS = (
    "intruder", "attacker", "attack", "assault", "burglar", "break-in", "weapon",
    "suicide", "self-harm", "heart attack", "cardiac arrest", "stroke", "diagnosis",
    "dangerous", "suspicious",
)
_CONFIRMED = "confirmed"

_TITLES = {
    EventKind.POSSIBLE_FALL: "Possible fall: a burst of movement followed by stillness",
    EventKind.LONG_STILLNESS: "No movement for longer than usual",
    EventKind.AWAY_MOVEMENT: "Movement detected while you are marked as away",
    EventKind.INTENSE_MOVEMENT: "Sudden intense movement",
    EventKind.MISSED_CHECKIN: "The daily check-in was not answered",
    EventKind.NOT_WATCHING: "PGuard is not watching: sensing data stopped arriving",
}


# Irregular forms that a plain suffix cannot produce.
_EXTRA_FORMS = {"diagnosis": ("diagnoses",)}
_SUFFIXES = "(?:s|es|ed|ing)?"


def _pattern(term: str) -> re.Pattern[str]:
    """Match the term and its plural or verb forms ("intruders", "assaulted", "break-ins")."""
    forms = "|".join(re.escape(f) for f in (term, *_EXTRA_FORMS.get(term, ())))
    return re.compile(rf"(?<![\w-])(?:{forms}){_SUFFIXES}(?![\w-])", re.IGNORECASE)


_PATTERNS = {term: _pattern(term) for term in BANNED_TERMS}
_CONFIRMED_PATTERN = re.compile(rf"(?<![\w-]){_CONFIRMED}(?![\w-])", re.IGNORECASE)


def check_wording(text: str, confirmed: bool) -> list[str]:
    """Return every banned term found in `text`; an empty list means the text is acceptable."""
    found = [t for t in BANNED_TERMS if _PATTERNS[t].search(text)]
    if not confirmed and _CONFIRMED_PATTERN.search(text):
        found.append(_CONFIRMED)
    return found


def describe(kind: EventKind, evidence: str, confidence: float, research: bool) -> str:
    mode = " Research mode: accuracy in this home is not established." if research else ""
    return (f"{_TITLES[kind]}. Evidence: {evidence}. Confidence: {confidence:.0%}. "
            f"This is an automated estimate; a person has not checked it yet.{mode}")
