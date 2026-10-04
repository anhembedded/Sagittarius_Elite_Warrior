"""An attributed quote must be text the cited document actually contains.

A quotation carries the cited file's authority; an invented one borrows it for
words nobody wrote (the 2026-10-04 audit found one). Only explicitly attributed
quotes are checked -- `"Q" (DOCREF …)`, `(DOCREF …): "Q"`, `DOCREF §N "Q"` and
`DOCREF §N's "Q"` -- with Q at least eight characters. Both sides are normalised
(NFKC, case, quote and dash forms, emphasis markers, whitespace) and Q must be a
substring of the cited section, of the nth invariant for `CONSTITUTION Pn`, or of
the whole document when no section is named.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator

from .citations import Citation, Reference, scan_line
from .invariants import CONSTITUTION, invariants
from .markdown import LineKind, classify
from .outline import SectionIndex
from .problems import Problem
from .repository import Repository
from .trees import PROMPT_TREES, collect

_QUOTE = r"[\"“](?P<quote>[^\"“”\n]{8,})[\"”]"
_QUOTE_THEN_PAREN = re.compile(_QUOTE + r"\s*\((?P<paren>[^()\n]+)\)")
_PAREN_THEN_QUOTE = re.compile(r"\((?P<paren>[^()\n]+)\):\s*" + _QUOTE)
_QUOTE_AFTER_CITATION = re.compile(r"(?:'s)?\s*" + _QUOTE)
_INVARIANT = re.compile(r"\s*P(\d+)\b")
_FOLD = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})
_DROPPED = re.compile(r"[*_`]")


def normalise(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).lower().translate(_FOLD)
    return " ".join(_DROPPED.sub("", folded).split())


class _Bodies:
    """The text a quote is checked against, per (document, anchor, invariant)."""

    def __init__(self, repository: Repository) -> None:
        self._repository = repository
        self._sections = SectionIndex(repository)
        self._invariants = invariants(repository)

    def of(
        self, document: str, anchor: str | None, invariant: int | None
    ) -> str | None:
        """The cited text, or None when the citation itself is broken (citations reports it)."""
        if anchor is not None:
            section = self._sections.of(document).get(anchor)
            return section.body if section else None
        if invariant is not None:
            if document != CONSTITUTION or not 1 <= invariant <= len(self._invariants):
                return None
            return self._invariants[invariant - 1]
        return self._repository.text(document)


def _attribution(
    repository: Repository, source: str, paren: str
) -> tuple[str, str | None, int | None] | None:
    """(document, anchor, invariant) when `paren` opens with a document reference."""
    text = paren.strip()
    found = list(scan_line(repository, source, text))
    if not found or not isinstance(found[0], Reference) or found[0].start != 0:
        return None
    reference = found[0]
    if reference.document is None:
        return None
    following = found[1] if len(found) > 1 else None
    if isinstance(following, Citation) and following.document == reference.document:
        return (
            reference.document,
            following.anchors[0] if following.anchors else None,
            None,
        )
    invariant = _INVARIANT.match(text, reference.end)
    return reference.document, None, int(invariant.group(1)) if invariant else None


def attributed_quotes(
    repository: Repository, source: str, line: str
) -> Iterator[tuple[str, str, str | None, int | None]]:
    """(quote, document, anchor, invariant) for every attributed quote on `line`."""
    seen: set[int] = set()
    for pattern in (_QUOTE_THEN_PAREN, _PAREN_THEN_QUOTE):
        for match in pattern.finditer(line):
            cited = _attribution(repository, source, match.group("paren"))
            if cited is not None and match.start("quote") not in seen:
                seen.add(match.start("quote"))
                yield (match.group("quote"), *cited)
    for found in scan_line(repository, source, line):
        if (
            not isinstance(found, Citation)
            or found.document is None
            or not found.anchors
        ):
            continue
        after = _QUOTE_AFTER_CITATION.match(line, found.end)
        if after and after.start("quote") not in seen:
            seen.add(after.start("quote"))
            yield after.group("quote"), found.document, found.anchors[0], None


def check_quotes(repository: Repository) -> list[Problem]:
    bodies = _Bodies(repository)
    root = repository.root
    problems: list[Problem] = []
    for path in collect(root, PROMPT_TREES):
        source = path.relative_to(root).as_posix()
        for line in classify(path.read_text(encoding="utf-8")):
            if line.kind is LineKind.CODE:
                continue
            for quote, document, anchor, invariant in attributed_quotes(
                repository, source, line.text
            ):
                body = bodies.of(document, anchor, invariant)
                if body is not None and normalise(quote) not in normalise(body):
                    where = (
                        f" §{anchor}"
                        if anchor
                        else f" P{invariant}"
                        if invariant
                        else ""
                    )
                    message = f'"{quote}" is not in `{document}`{where}'
                    problems.append(Problem("quotes", source, line.number, message))
    return problems
