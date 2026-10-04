"""Every `§` citation names a document that exists and a section that document has.

A reader told "see `ci-rule.md` §7" opens §7 and, finding none, guesses -- the
citation outlived the renumbering that broke it. A citation is a document
reference followed by `§ANCHOR` (or a range `§A–§B`, both ends checked); a bare
`§N` binds to the last document named earlier on its line, else to the file it is
written in. Citations of the HLD, SDD or an ADR are skipped and counted: those
documents number their sections in a way this check does not model.
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .markdown import LineKind, classify
from .outline import ANCHOR, SectionIndex
from .problems import Problem
from .repository import Repository
from .trees import CITATION_TREES, collect

ALIASES: dict[str, str] = {
    "ONBOARDING": ".claude/ONBOARDING.md",
    "CONSTITUTION": ".claude/CONSTITUTION.md",
    "CLAUDE": "CLAUDE.md",
}

_TOKEN = re.compile(
    r"\[[^\]\n]*\]\((?P<link>[^)\s]+)\)"
    r"|`(?P<tick>[^`\n]+)`"
    r"|(?<![\w/.-])(?P<bare>(?:[\w.-]+/)*[\w-][\w.-]*\.md)\b"
    r"|\b(?P<alias>ONBOARDING|CONSTITUTION|CLAUDE)\b(?!\.md)"
    r"|§"
)
_CITE = re.compile(
    rf"§\s?({ANCHOR.pattern})(?:(?:[–-]§?|\s[–-]\s§)\s?({ANCHOR.pattern}))?"
)
_DOC_PATH = re.compile(r"[\w./-]+\.md")
_UNMODELLED = re.compile(r"\b(?:HLD|SDD|ADR)\s*$")


@dataclass(frozen=True)
class Reference:
    """A named document: its repository path, or why it does not resolve."""

    start: int
    end: int
    document: str | None
    error: str | None


@dataclass(frozen=True)
class Citation:
    """`§ANCHOR` bound to a document; `document` is None when skipped or in error."""

    start: int
    end: int
    document: str | None
    anchors: tuple[str, ...]
    error: str | None


def _by_name(
    repository: Repository, source: str, name: str
) -> tuple[str | None, str | None]:
    """(document, None) for the one document `name` names from `source`, else (None, why)."""
    name = name.removeprefix("./")
    relative = posixpath.normpath(posixpath.join(posixpath.dirname(source), name))
    for candidate in (name, relative):
        if repository.holds(candidate):
            return candidate, None
    matches = repository.find_by_suffix(name)
    if len(matches) == 1:
        return matches[0], None
    if not matches:
        return None, f"`{name}` names no document in the repository"
    return None, f"`{name}` is ambiguous ({', '.join(matches)})"


def _reference(
    repository: Repository, source: str, token: re.Match[str]
) -> Reference | None:
    """The document `token` names, or None when it names none (code, a URL, a non-.md path)."""
    if token.group("alias"):
        return Reference(
            token.start(), token.end(), ALIASES[token.group("alias")], None
        )
    if token.group("link"):
        target = token.group("link").split("#", 1)[0]
        if not target.endswith(".md") or "://" in target:
            return None
        path = posixpath.normpath(posixpath.join(posixpath.dirname(source), target))
        if path.startswith(".."):
            return None
        if repository.holds(path):
            return Reference(token.start(), token.end(), path, None)
        return Reference(
            token.start(), token.end(), None, f"link `{target}` names no document"
        )
    name = token.group("tick") or token.group("bare")
    if not _DOC_PATH.fullmatch(name):
        return None
    document, error = _by_name(repository, source, name)
    return Reference(token.start(), token.end(), document, error)


def _bind(
    source: str, line: str, last: Reference | None, cite: re.Match[str]
) -> Citation:
    """Bind a well-formed `§` to the document it cites (module docstring's rule)."""
    start, end = cite.start(), cite.end()
    anchors = tuple(anchor for anchor in cite.groups() if anchor)
    if _UNMODELLED.search(line[:start]):
        return Citation(start, end, None, anchors, None)
    if last is not None:
        return Citation(start, end, last.document, anchors, last.error)
    return Citation(
        start, end, source if source.endswith(".md") else None, anchors, None
    )


def scan_line(
    repository: Repository, source: str, line: str
) -> Iterator[Reference | Citation]:
    """The references and citations of one line, in order."""
    last: Reference | None = None
    position = 0
    while (token := _TOKEN.search(line, position)) is not None:
        position = token.end()
        if token.group() != "§":
            reference = _reference(repository, source, token)
            if reference is not None:
                last = reference
                yield reference
            continue
        cite = _CITE.match(line, token.start())
        if cite is None:
            message = "`§` is not followed by a section number"
            yield Citation(token.start(), token.end(), None, (), message)
            continue
        position = cite.end()
        yield _bind(source, line, last, cite)


def document_lines(path: Path) -> Iterator[tuple[int, str]]:
    """(number, text) of every line a citation can be written on."""
    text = path.read_text(encoding="utf-8")
    if path.suffix != ".md":
        yield from enumerate(text.splitlines(), start=1)
        return
    for line in classify(text):
        if line.kind is not LineKind.CODE:
            yield line.number, line.text


def _citations(repository: Repository) -> Iterator[tuple[str, int, Citation]]:
    root = repository.root
    for path in collect(root, CITATION_TREES):
        source = path.relative_to(root).as_posix()
        for number, text in document_lines(path):
            for found in scan_line(repository, source, text):
                if isinstance(found, Citation):
                    yield source, number, found


def check_citations(repository: Repository) -> list[Problem]:
    index = SectionIndex(repository)
    problems: list[Problem] = []
    for source, number, citation in _citations(repository):
        if citation.error is not None:
            problems.append(Problem("citations", source, number, citation.error))
            continue
        if citation.document is None:
            continue
        for anchor in citation.anchors:
            if anchor not in index.of(citation.document):
                message = f"`{citation.document}` has no §{anchor}"
                problems.append(Problem("citations", source, number, message))
    return problems


def count_skipped(repository: Repository) -> int:
    """Citations not checked: of the HLD, SDD or an ADR, or bound to no document."""
    return sum(
        1
        for _, _, citation in _citations(repository)
        if citation.document is None and citation.error is None
    )
