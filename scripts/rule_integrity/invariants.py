"""Every `Pn` names an invariant `CONSTITUTION.md` defines, and `P1–Pn` spans them all.

The invariants are the numbered items under the Constitution's `## The
Invariants` heading, counted rather than hard-coded: a rule citing P12 when there
are eleven, or "all invariants (P1–P10)" after an eleventh was added, cites a law
that does not exist or forgets one that does.
"""

from __future__ import annotations

import re

from .markdown import LineKind, classify
from .outline import numbered_items_under
from .problems import Problem
from .repository import Repository
from .trees import PROMPT_TREES, collect

CONSTITUTION = ".claude/CONSTITUTION.md"
INVARIANTS_HEADING = "The Invariants"

_CODE_SPAN = re.compile(r"`([^`\n]*)`")
_PLAIN_REF = re.compile(r"P\d+")
_REF = re.compile(r"(?:^|(?<=[\s(,]))P(\d+)(?:\s?[–-]\s?P(\d+))?(?![\w])")


def invariants(repository: Repository) -> list[str]:
    """The body of each invariant, P1 first; empty when there is no Constitution."""
    if not (repository.root / CONSTITUTION).is_file():
        return []
    return numbered_items_under(repository.text(CONSTITUTION), INVARIANTS_HEADING)


def _without_code(line: str) -> str:
    """`line` with every code span blanked, except one that is a plain `P6`."""
    return _CODE_SPAN.sub(
        lambda span: span.group(1) if _PLAIN_REF.fullmatch(span.group(1)) else " ",
        line,
    )


def ref_problems(line: str, count: int) -> list[str]:
    problems: list[str] = []
    for ref in _REF.finditer(_without_code(line)):
        first = int(ref.group(1))
        last = int(ref.group(2)) if ref.group(2) else None
        for number in (first, last):
            if number is not None and not 1 <= number <= count:
                problems.append(
                    f"P{number} does not exist: the Constitution defines P1–P{count}"
                )
        if first == 1 and last is not None and last != count:
            problems.append(
                f"P1–P{last} is not every invariant: the Constitution defines P1–P{count}"
            )
    return problems


def check_invariant_refs(repository: Repository) -> list[Problem]:
    count = len(invariants(repository))
    if count == 0:
        if not (repository.root / CONSTITUTION).is_file():
            return []
        # An empty parse is a renamed heading or a reformatted list, never "no
        # invariants": passing silently here would switch the check off.
        return [
            Problem(
                "invariant refs",
                CONSTITUTION,
                1,
                f"no numbered invariants under {INVARIANTS_HEADING!r}; "
                "the Pn checks would pass without checking anything",
            )
        ]
    root = repository.root
    problems: list[Problem] = []
    for path in collect(root, PROMPT_TREES):
        source = path.relative_to(root).as_posix()
        for line in classify(path.read_text(encoding="utf-8")):
            if line.kind is LineKind.CODE:
                continue
            for message in ref_problems(line.text, count):
                problems.append(Problem("invariant refs", source, line.number, message))
    return problems
