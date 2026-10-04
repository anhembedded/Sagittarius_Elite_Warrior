"""Every `[review: ID]` tag must name an ID the pr-review rubric defines."""

from __future__ import annotations

import re
from pathlib import Path

from .problems import Problem
from .repository import Repository
from .trees import PROMPT_TREES, collect

#: The inspection rubric defining every valid review ID (A1-N8).
RUBRIC_PATH = Path(".claude") / "skills" / "pr-review" / "references" / "rubric.md"

_BRACKETED_CLAUSE = re.compile(r"\[([^\]\n]+)\]")
_REVIEW_TAG = re.compile(r"\breview:\s*([^;\]\n]+)")
_RUBRIC_ID_PATTERN = re.compile(r"^\|\s*\*\*([A-N]\d+)\*\*", re.MULTILINE)
_IGNORED_REVIEW_TAGS = {"row"}


def load_rubric_ids(root: Path) -> set[str]:
    """Extract valid checklist IDs (e.g. A1, M6) from the pr-review rubric."""
    rubric_file = root / RUBRIC_PATH
    if not rubric_file.is_file():
        return set()
    return set(_RUBRIC_ID_PATTERN.findall(rubric_file.read_text(encoding="utf-8")))


def _extract_review_tags(text: str) -> list[str]:
    tags: list[str] = []
    for clause in _BRACKETED_CLAUSE.findall(text):
        for match in _REVIEW_TAG.finditer(clause):
            for raw_tag in match.group(1).split(","):
                tag = raw_tag.strip().strip("`").strip()
                if tag:
                    tags.append(tag)
    return tags


def check_review_tags(repository: Repository) -> list[Problem]:
    """Every `[review: ID]` whose ID the rubric does not define."""
    root = repository.root
    rubric_file = root / RUBRIC_PATH
    if not rubric_file.is_file():
        return []
    valid_ids = load_rubric_ids(root)
    if not valid_ids:
        return [
            Problem("review tags", RUBRIC_PATH.as_posix(), 1, "holds no rubric IDs")
        ]
    problems: list[Problem] = []
    for source in collect(root, PROMPT_TREES):
        if source.resolve() == rubric_file.resolve():
            continue
        for tag in _extract_review_tags(source.read_text(encoding="utf-8")):
            if tag not in _IGNORED_REVIEW_TAGS and tag not in valid_ids:
                relative = source.relative_to(root).as_posix()
                problems.append(Problem("review tags", relative, 1, f"[review: {tag}]"))
    return problems
