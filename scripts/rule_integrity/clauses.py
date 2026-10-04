"""Every clause of a rule file ends with the tag naming what enforces it.

A rule an agent must obey but no mechanism checks is a rule held by memory alone,
which `CONSTITUTION.md` P1 forbids. The tag (`[guard: …]`, `[gate: …]`,
`[review: …]`, `[eye]`, `[contract: …]`) is the clause's claim about its own
enforcement; `tags.py` then checks that claim is true.

Exempt: the role sentence (the first sentence of the first block after the H1,
when it reads "You are …"; any further sentence in that block is a clause), an
untagged lead-in (a clause ending with `:` that a list item follows directly),
and the items of a list that a *tagged* lead-in introduces -- the lead-in's tag
covers them. A clause ending with `:` that no list follows is an ordinary clause.
Table rows are not clauses: an obligation written as a table row is outside this
check, which `.claude/README.md` states where it promises tagged clauses.
"""

from __future__ import annotations

import re

from .markdown import Clause, clauses
from .problems import Problem
from .repository import Repository
from .trees import rule_files

#: A clause's closing tag, written in backticks, optionally followed by a full stop.
CLOSING_TAG = re.compile(r"`\[(?:guard|gate|review|eye|contract)\b[^\]`\n]*\]`\.?\s*$")

_EXCERPT = 60


def _is_lead_in(clause: Clause) -> bool:
    return CLOSING_TAG.sub("", clause.text).rstrip().endswith(":")


def _is_tagged(clause: Clause) -> bool:
    return CLOSING_TAG.search(clause.text) is not None


def _is_role_sentence_only(clause: Clause) -> bool:
    """The opening "You are …" block, when it holds nothing but that sentence."""
    if not (clause.opens_document and clause.text.startswith("You are ")):
        return False
    _, _, rest = clause.text.partition(". ")
    return not rest.strip()


def _introduces_a_list(found: list[Clause], index: int) -> bool:
    following = found[index + 1] if index + 1 < len(found) else None
    return following is not None and following.is_item and not following.after_barrier


def untagged_clauses(text: str) -> list[Clause]:
    """The clauses of one rule file that carry no closing tag and are not exempt."""
    found = clauses(text)
    untagged: list[Clause] = []
    covered = False
    for index, clause in enumerate(found):
        covered = covered and clause.is_item and not clause.after_barrier
        if _is_lead_in(clause) and _introduces_a_list(found, index):
            covered = _is_tagged(clause)
            continue
        exempt = covered or _is_role_sentence_only(clause)
        if not exempt and not _is_tagged(clause):
            untagged.append(clause)
    return untagged


def _excerpt(text: str) -> str:
    return text if len(text) <= _EXCERPT else text[: _EXCERPT - 1] + "…"


def check_clause_tags(repository: Repository) -> list[Problem]:
    root = repository.root
    problems: list[Problem] = []
    for source in rule_files(root):
        relative = source.relative_to(root).as_posix()
        for clause in untagged_clauses(source.read_text(encoding="utf-8")):
            problems.append(
                Problem(
                    "clause tags",
                    relative,
                    clause.line,
                    f"clause names no enforcing mechanism: {_excerpt(clause.text)!r}",
                )
            )
    return problems
