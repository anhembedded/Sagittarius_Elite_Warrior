"""Fail when a prompt names a repository path that is gone.

Every document under `.claude/` is read by a session that follows its links
without doubting them, so a stale one keeps a reader hunting for what the
repository deleted -- a scheduled agent's briefing spent months citing a rule
file that never existed (`EPIC-011` is the record). This is the mechanical half
of "a path is checked before it is cited": it cannot tell that a *claim* went
stale, but it does catch a document pointing at something that is not there.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from .problems import Problem
from .repository import Repository, open_repository
from .trees import PROMPT_TREES, collect

#: Repository-root directories this check claims authority over. A reference is
#: only verified when it starts with one of these, which is what lets the prompts
#: keep talking about `package.json` (to say the repo has none) and about
#: `sagittarius_engine/` (a separate repository) without either being reported.
#: Every entry means "a path under here is expected to exist in this checkout".
CHECKED_ROOTS = (
    ".claude/",
    ".github/",
    "Docs/",
    "Tasks/",
    "scripts/",
    "src/",
    "tests/",
)

#: Characters that mean the backticked span is a shell command, a glob, or a
#: placeholder such as `.claude/skills/<name>/SKILL.md` or a template's
#: `Tasks/backlog/BOT-{nnn}_{slug}.md` -- never a literal path to verify.
_NOT_A_LITERAL_PATH = re.compile(r"""[\s*?<>|$"'()\[\]{}]|::|https?:""")

_BACKTICKED = re.compile(r"`([^`\n]+)`")
_MARKDOWN_LINK = re.compile(r"\[[^\]\n]*\]\(([^)\n]+)\)")


def _is_verifiable(candidate: str) -> bool:
    """True when `candidate` claims a path this checkout must contain."""
    if _NOT_A_LITERAL_PATH.search(candidate):
        return False
    return candidate.startswith(CHECKED_ROOTS)


def _backticked_references(text: str) -> list[str]:
    return [span for span in _BACKTICKED.findall(text) if _is_verifiable(span)]


def _link_references(text: str, source: Path, root: Path) -> list[str]:
    """Markdown link targets, normalised to repository-relative form.

    A link is written relative to the file that carries it, so it is resolved
    against `source.parent` before being compared with `CHECKED_ROOTS` -- which
    is what lets one function serve trees at different depths.
    """
    references: list[str] = []
    for raw_target in _MARKDOWN_LINK.findall(text):
        target = raw_target.split("#", 1)[0].strip()
        if not target or _NOT_A_LITERAL_PATH.search(target):
            continue
        resolved = (source.parent / target).resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError:
            # Points outside the repository -- not this checker's business.
            continue
        if relative.startswith(CHECKED_ROOTS):
            references.append(relative)
    return references


def missing_references(repository: Repository) -> list[tuple[Path, str]]:
    """Every (source file, missing path) pair across `PROMPT_TREES`."""
    root = repository.root
    missing: list[tuple[Path, str]] = []
    for source in collect(root, PROMPT_TREES):
        text = source.read_text(encoding="utf-8")
        references = _backticked_references(text) + _link_references(text, source, root)
        # A document naturally names the same path more than once; report once.
        for reference in dict.fromkeys(references):
            if not repository.holds(reference):
                missing.append((source.relative_to(root), reference))
    return missing


def check(root: Path) -> list[tuple[Path, str]]:
    """Every (source file, missing path) pair, asked of git when git can answer."""
    repository = open_repository(root)
    if repository.tracked is None:
        print(
            "warning: git could not list this tree, so paths are being checked "
            "against the working directory. An untracked leftover will read as "
            "present here and missing in CI (`BUG-129`).",
            file=sys.stderr,
        )
    return missing_references(repository)


def _first_line(text: str, reference: str) -> int:
    """The line that first names `reference`, or its file name for a relative link."""
    for needle in (reference, reference.rsplit("/", 1)[-1]):
        for number, line in enumerate(text.splitlines(), start=1):
            if needle in line:
                return number
    return 1


def check_paths(repository: Repository) -> list[Problem]:
    """`missing_references` as problems, for the CLI's uniform report."""
    return [
        Problem(
            "paths",
            source.as_posix(),
            _first_line(repository.text(source.as_posix()), reference),
            f"`{reference}` is not in the repository",
        )
        for source, reference in missing_references(repository)
    ]
