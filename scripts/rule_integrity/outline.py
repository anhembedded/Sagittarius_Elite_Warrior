"""A document's numbered anchors -- what a `§` citation can point at.

Anchors are numbered headings ("1", "1b", "2.1", "6.5", "7.2.1") and the
top-level numbered items under them ("5.3"); in a document with no numbered
heading, the top-level numbered items themselves ("3").
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .markdown import HEADING, TOP_LEVEL_ITEM, Line, LineKind, classify, is_heading
from .repository import Repository

_Predicate = Callable[[str], bool]

_NUMBERED_ITEM = re.compile(r"^(\d+)\.\s")
_ANCHOR = r"\d+(?:[a-z](?![a-z]))?(?:\.\d+(?:[a-z](?![a-z]))?)*"
_NUMBERED_HEADING = re.compile(rf"^#{{1,6}}\s+§?\s*({_ANCHOR})\.?\s")
ANCHOR = re.compile(_ANCHOR)


@dataclass(frozen=True)
class Section:
    line: int
    body: str


def sections(text: str) -> dict[str, Section]:
    """Every numbered anchor of `text` -> its line and body (module docstring)."""
    lines = [line for line in classify(text) if line.kind is not LineKind.CODE]
    numbered = any(
        is_heading(line.text) and _heading_anchor(line.text) for line in lines
    )
    found: dict[str, Section] = {}
    heading_anchor: str | None = None
    for index, line in enumerate(lines):
        if is_heading(line.text):
            heading_anchor = _heading_anchor(line.text)
            if heading_anchor:
                body = _body(lines, index, _ends_section(_heading_level(line.text)))
                found.setdefault(heading_anchor, Section(line.number, body))
            continue
        item = _NUMBERED_ITEM.match(line.text)
        if item is None or (numbered and heading_anchor is None):
            continue
        anchor = f"{heading_anchor}.{item.group(1)}" if numbered else item.group(1)
        body = _body(lines, index, _ends_item)
        found.setdefault(anchor, Section(line.number, body))
    return found


def numbered_items_under(text: str, title: str) -> list[str]:
    """The bodies of the top-level numbered items under the heading named `title`."""
    lines = [line for line in classify(text) if line.kind is not LineKind.CODE]
    items: list[str] = []
    inside = False
    for index, line in enumerate(lines):
        if is_heading(line.text):
            inside = line.text.strip().lstrip("#").strip() == title
        elif inside and _NUMBERED_ITEM.match(line.text):
            items.append(_body(lines, index, _ends_item))
    return items


def _heading_anchor(text: str) -> str | None:
    match = _NUMBERED_HEADING.match(text.strip() + " ")
    return match.group(1) if match else None


def _ends_section(level: int) -> _Predicate:
    """A heading of `level` or above ends the section a heading of `level` opens."""
    return lambda text: 0 < _heading_level(text) <= level


def _ends_item(text: str) -> bool:
    return is_heading(text) or TOP_LEVEL_ITEM.match(text) is not None


def _heading_level(text: str) -> int:
    match = HEADING.match(text)
    return len(match.group(1)) if match else 0


def _body(lines: list[Line], start: int, ends: _Predicate) -> str:
    body = [lines[start].text]
    for line in lines[start + 1 :]:
        if ends(line.text):
            break
        body.append(line.text)
    return "\n".join(body)


class SectionIndex:
    """Each cited document's anchors, parsed once per run."""

    def __init__(self, repository: Repository) -> None:
        self._repository = repository
        self._cache: dict[str, dict[str, Section]] = {}

    def of(self, document: str) -> dict[str, Section]:
        if document not in self._cache:
            self._cache[document] = sections(self._repository.text(document))
        return self._cache[document]
