"""A stretch of a message with a meaning: a value the code substituted, or a tag."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SpanRole(Enum):
    #: A value the log call substituted, known exactly from the call's template.
    PARAM = "param"
    #: A word that looks like a value, guessed when no template fits the line.
    GUESS = "guess"
    #: A bracket tag such as `[health]`.
    TAG = "tag"


@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int
    role: SpanRole
