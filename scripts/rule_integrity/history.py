"""A rule states what holds now; how it came to hold belongs in a decision record.

Dates and pull-request numbers in a rule are history: they age, they are copied
into the next rule, and a reader cannot tell a still-binding clause from a story.
The decision itself lives in a `DECISION_*.md`, which a rule can cite. Fenced
blocks are exempt -- a command may legitimately carry a date.
"""

from __future__ import annotations

import re

from .markdown import LineKind, classify
from .problems import Problem
from .repository import Repository
from .trees import history_free_files

_HISTORY = re.compile(r"\b20\d\d-\d\d-\d\d\b|\bPR #\d+\b")


def history_problems(text: str) -> list[tuple[int, str]]:
    """(line, message) for every date or PR number outside a fenced block."""
    found: list[tuple[int, str]] = []
    for line in classify(text):
        if line.kind is LineKind.CODE:
            continue
        for match in _HISTORY.finditer(line.text):
            found.append(
                (
                    line.number,
                    f"`{match.group()}` is history: record it in a DECISION_*.md, not in a rule",
                )
            )
    return found


def check_history(repository: Repository) -> list[Problem]:
    root = repository.root
    problems: list[Problem] = []
    for path in history_free_files(root):
        source = path.relative_to(root).as_posix()
        for number, message in history_problems(path.read_text(encoding="utf-8")):
            problems.append(Problem("history", source, number, message))
    return problems
