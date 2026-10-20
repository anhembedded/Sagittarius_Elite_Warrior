"""The coloured parts of one message: its exact params when a template fits, else guesses.

Tags win over guesses (a `[health]` is never a value); an exact param wins over a
tag-looking word inside it (the text of an exception that happens to hold
`['a']`). A hole whose text is itself a bracket tag (an f-string's `{_TAG}`) is the
tag, not a param.
"""

from __future__ import annotations

import re

from Sagittarius_Elite_Warrior.src.support.log_view.param_span import Span, SpanRole
from Sagittarius_Elite_Warrior.src.support.log_view.template_matcher import (
    TemplateMatcher,
)

_TAG = re.compile(r"\[[a-z0-9][a-z0-9-]*\]|\bBACKTEST_TRACE\b")
_BOT = re.compile(r"\bBot ([a-z0-9]{6})\b")
_KEY_VALUE = re.compile(r"\b[A-Za-z_][\w.-]*=([^\s;)]*[^\s,;)])")
_NUMBER = re.compile(r"(?<![\w.\[-])-?\d+(?:\.\d+)?(?:[a-zA-Z%]{1,3})?(?![\w\]])")


def message_spans(message: str, matcher: TemplateMatcher) -> tuple[Span, ...]:
    """Non-overlapping spans of `message`, in order."""
    exact = matcher.values_in(message)
    if exact is None:
        return _guessed(message)
    params = [Span(start, end, SpanRole.PARAM) for start, end in exact]
    spans = [_as_tag_if_tag(message, span) for span in params]
    for tag in _tags(message):
        if not any(_overlaps(tag, other) for other in spans):
            spans.append(tag)
    return tuple(sorted(spans, key=lambda s: s.start))


def _guessed(message: str) -> tuple[Span, ...]:
    spans = list(_tags(message))
    for pattern in (_BOT, _KEY_VALUE, _NUMBER):
        for found in pattern.finditer(message):
            group = 1 if pattern.groups else 0
            candidate = Span(found.start(group), found.end(group), SpanRole.GUESS)
            if not any(_overlaps(candidate, other) for other in spans):
                spans.append(candidate)
    return tuple(sorted(spans, key=lambda s: s.start))


def _tags(message: str) -> list[Span]:
    return [Span(f.start(), f.end(), SpanRole.TAG) for f in _TAG.finditer(message)]


def _as_tag_if_tag(message: str, span: Span) -> Span:
    if _TAG.fullmatch(message[span.start : span.end]):
        return Span(span.start, span.end, SpanRole.TAG)
    return span


def _overlaps(a: Span, b: Span) -> bool:
    return a.start < b.end and b.start < a.end
