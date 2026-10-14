"""A `fix:` pull request states its root cause, its corrective action and a before/after sequence (`BOT-180`).

`fix-bug-rule.md` §6.1 puts the four sections on the pull request itself, because
the pull request is where the owner reads a fix. CI runs this script on every
`pull_request` event (`.github/workflows/commit-lint.yml`): when the title starts
with `fix`, the body must carry `## Root cause`, `## Corrective action`,
`## Sequence: before` and `## Sequence: after`, each filled in. A Sequence section
holds either a fenced `mermaid` block containing `sequenceDiagram`, or the single
line `Not applicable: <reason>` for a defect with no interaction to draw. Whether
the diagram is *true* is a reviewer's call (rubric E16); Mermaid syntax is not
validated here, because GitHub renders the block and the reader sees a broken one.

The title and body arrive through the environment (`PR_TITLE`, `PR_BODY`), never
interpolated into a shell command. Stdlib only, so it runs on the runner's Python.

Retire when: the repository adopts a pull-request body linter in the same workflow.
"""

from __future__ import annotations

import os
import re
import sys

ROOT_CAUSE = "Root cause"
CORRECTIVE_ACTION = "Corrective action"
SEQUENCE_BEFORE = "Sequence: before"
SEQUENCE_AFTER = "Sequence: after"
REQUIRED_HEADINGS = (ROOT_CAUSE, CORRECTIVE_ACTION, SEQUENCE_BEFORE, SEQUENCE_AFTER)
_SEQUENCE_HEADINGS = (SEQUENCE_BEFORE, SEQUENCE_AFTER)

_FIX_TITLE = re.compile(r"^\s*fix\b", re.IGNORECASE)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_HEADING = re.compile(r"^##[ \t]+(?P<name>\S.*?)[ \t]*#*[ \t]*$")
_FENCE = re.compile(r"^[ \t]*(?P<mark>`{3,}|~{3,})[ \t]*(?P<info>[\w-]*)")
_NOT_APPLICABLE = re.compile(r"^Not applicable: \S", re.IGNORECASE)


def is_fix_title(title: str) -> bool:
    """True when the pull request title starts with `fix` (`fix:`, `fix(scope):`, `fix!:`)."""
    return _FIX_TITLE.match(title) is not None


def _sections(body: str) -> dict[str, list[str]]:
    """Level-2 sections by lower-cased heading; a `## ` line inside a fenced block is content."""
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    fence = ""
    for line in _COMMENT.sub("", body).splitlines():
        opening = _FENCE.match(line)
        if opening and not fence:
            fence = opening.group("mark")
        elif opening and line.strip().startswith(fence) and not opening.group("info"):
            fence = ""
        heading = None if fence else _HEADING.match(line)
        if heading:
            current = sections.setdefault(heading.group("name").lower(), [])
        elif current is not None:
            current.append(line)
    return sections


def _has_mermaid_sequence(lines: list[str]) -> bool:
    inside = False
    for line in lines:
        opening = _FENCE.match(line)
        if opening and not inside:
            inside = opening.group("info").lower() == "mermaid"
        elif opening and inside:
            inside = False
        elif inside and line.strip() == "sequenceDiagram":
            return True
    return False


def _is_filled(lines: list[str]) -> bool:
    return any(line.strip() for line in lines)


def problems(title: str, body: str) -> list[str]:
    """What a `fix:` pull request is missing under `fix-bug-rule.md` §6.1; empty otherwise."""
    if not is_fix_title(title):
        return []
    sections = _sections(body)
    found: list[str] = []
    for heading in REQUIRED_HEADINGS:
        lines = sections.get(heading.lower())
        if lines is None:
            found.append(f"missing the `## {heading}` section")
        elif not _is_filled(lines):
            found.append(f"the `## {heading}` section is empty")
        elif heading in _SEQUENCE_HEADINGS and not (
            _has_mermaid_sequence(lines)
            or any(_NOT_APPLICABLE.match(line.strip()) for line in lines)
        ):
            found.append(
                f"`## {heading}` has neither a ```mermaid block with `sequenceDiagram` "
                "nor a `Not applicable: <reason>` line"
            )
    return found


def main() -> int:
    title = os.environ.get("PR_TITLE", "")
    body = os.environ.get("PR_BODY", "")
    if not is_fix_title(title):
        print(f"OK: {title!r} is not a fix pull request; nothing to check.")
        return 0
    found = problems(title, body)
    for problem in found:
        print(f"fix pull request body: {problem} (fix-bug-rule.md §6.1)")
    if found:
        print(
            f"\n{len(found)} problem(s); fill them in on the pull request description.",
            file=sys.stderr,
        )
        return 1
    print(
        "OK: the fix pull request carries root cause, corrective action and both sequences."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
