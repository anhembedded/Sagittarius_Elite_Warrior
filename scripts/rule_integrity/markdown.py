"""The small slice of Markdown the checks need: prose lines and clauses.

Front matter, fenced blocks (``` and ~~~) and HTML comments are never prose: a
command in a fence is not a rule, and a comment is not read as one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class LineKind(Enum):
    PROSE = "prose"
    CODE = "code"
    META = "meta"


@dataclass(frozen=True)
class Line:
    number: int
    text: str
    kind: LineKind


@dataclass(frozen=True)
class Clause:
    """One obligation-sized block: a top-level list item with its folded lines, or a paragraph.

    `after_barrier` is true when a heading, table, fence or rule separates it from
    the clause before; `opens_document` marks the first clause after the H1.
    """

    line: int
    text: str
    is_item: bool
    after_barrier: bool
    opens_document: bool


_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
_COMMENT = re.compile(r"<!--.*?-->")
HEADING = re.compile(r"^\s{0,3}(#{1,6})(?:\s|$)")
_HORIZONTAL_RULE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")
TOP_LEVEL_ITEM = re.compile(r"^(?:[-*]|\d+\.)\s")


def _front_matter_end(lines: list[str]) -> int:
    if not lines or lines[0].strip() != "---":
        return 0
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return index + 1
    return 0


def classify(text: str) -> list[Line]:
    """Every line of `text`, numbered from 1, marked prose, code or meta."""
    raw = text.splitlines()
    meta_end = _front_matter_end(raw)
    result: list[Line] = []
    fence: str | None = None
    in_comment = False
    for index, line in enumerate(raw):
        number = index + 1
        if index < meta_end:
            result.append(Line(number, line, LineKind.META))
            continue
        opener = _FENCE.match(line)
        if fence is not None:
            if (
                opener
                and opener.group(1)[0] == fence[0]
                and len(opener.group(1)) >= len(fence)
            ):
                fence = None
            result.append(Line(number, line, LineKind.CODE))
            continue
        if in_comment:
            in_comment = "-->" not in line
            result.append(Line(number, line, LineKind.META))
            continue
        if opener:
            fence = opener.group(1)
            result.append(Line(number, line, LineKind.CODE))
            continue
        visible = _COMMENT.sub("", line)
        if "<!--" in visible:
            in_comment = True
            visible = visible.split("<!--", 1)[0]
        result.append(Line(number, visible, LineKind.PROSE))
    return result


def is_heading(text: str) -> bool:
    return HEADING.match(text) is not None


def _barrier_text(stripped: str) -> bool:
    return stripped.startswith("|") or _HORIZONTAL_RULE.match(stripped) is not None


def clauses(text: str) -> list[Clause]:
    """The clauses of `text` in order; headings, tables, rules and blank lines are none."""
    found: list[Clause] = []
    parts: list[str] = []
    start = 0
    is_item = after_barrier = opens = False
    barrier = title_seen = pending_opening = False

    def flush() -> None:
        nonlocal parts
        if parts:
            found.append(Clause(start, " ".join(parts), is_item, after_barrier, opens))
        parts = []

    for line in classify(text):
        stripped = line.text.strip()
        if (
            line.kind is not LineKind.PROSE
            or is_heading(line.text)
            or _barrier_text(stripped)
        ):
            flush()
            barrier = True
            if (
                line.kind is LineKind.PROSE
                and stripped.startswith("# ")
                and not title_seen
            ):
                title_seen = pending_opening = True
            continue
        if not stripped:
            flush()
            continue
        if TOP_LEVEL_ITEM.match(line.text) or not parts:
            flush()
            start, is_item = line.number, TOP_LEVEL_ITEM.match(line.text) is not None
            after_barrier, opens = barrier, pending_opening
            barrier = pending_opening = False
        parts.append(stripped)
    flush()
    return found
