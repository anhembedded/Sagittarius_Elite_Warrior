"""Every commit a pull request adds follows `commit-rule.md` §2 (`EPIC-031A`).

`commit-rule.md` §2 sets the format: a Conventional Commit subject with an
allowed type, a body that explains the change, the `Co-Authored-By:` trailer,
and, for a `fix:`, the defect or task it repairs. Until this script those were
rubric rows L1-L3 that a reviewer read by eye; CI now runs it over the pull
request's own commits (`.github/workflows/commit-lint.yml`), so a message that
breaks the format fails the pull request rather than waiting for a reviewer.

Merge commits are skipped: GitHub writes them, and their format is GitHub's.
Stdlib only, no PEP 695 syntax, so it runs on the runner's system Python.

Retire when: a commit-message linter is adopted as a dependency and wired into
the same workflow.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass

ALLOWED_TYPES = ("feat", "fix", "refactor", "perf", "test", "ci", "docs", "chore")

_SUBJECT = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[a-z0-9][a-z0-9._/-]*)\))?!?: (?P<text>\S.*)$"
)
_TRAILER = re.compile(r"^[A-Za-z][A-Za-z-]*: \S")
_CO_AUTHOR = re.compile(r"^Co-Authored-By: .+$", re.MULTILINE)
#: The authoring session, so a commit names the session that wrote it.
_SESSION = re.compile(
    r"^Claude-Session: https://claude\.ai/code/session_[A-Za-z0-9]+$", re.MULTILINE
)
#: What a fix cites: a defect, task, epic child or proposal id, a case study, or
#: the pull request review that found it.
_FIX_REFERENCE = re.compile(
    r"\b(?:BUG|BOT|EPIC|PRO)-\d+[A-Z0-9]*\b|\bCS-\d+\b|\bPR #\d+\b", re.IGNORECASE
)
_RECORD_SEPARATOR = "\x1e"
_FIELD_SEPARATOR = "\x00"


@dataclass(frozen=True)
class Commit:
    sha: str
    message: str


def problems(message: str) -> list[str]:
    """What is wrong with one commit message under `commit-rule.md` §2; empty when it conforms."""
    lines = message.strip().splitlines()
    if not lines:
        return ["the message is empty"]
    subject = lines[0]
    found: list[str] = []
    match = _SUBJECT.match(subject)
    if match is None:
        found.append(
            f"subject {subject!r} is not `<type>(<scope>): <subject>` (commit-rule.md §2)"
        )
    elif match.group("type") not in ALLOWED_TYPES:
        found.append(
            f"type `{match.group('type')}` is not one of {', '.join(ALLOWED_TYPES)}"
        )
    body = [line for line in lines[1:] if line.strip() and not _TRAILER.match(line)]
    if not body:
        found.append(
            "the body is empty: explain what changed and why (commit-rule.md §2)"
        )
    if _CO_AUTHOR.search(message) is None:
        found.append("the `Co-Authored-By:` trailer is missing (commit-rule.md §2)")
    if _SESSION.search(message) is None:
        found.append(
            "the `Claude-Session:` trailer is missing; it names the session that "
            "wrote the commit (commit-rule.md §2)"
        )
    if match is not None and match.group("type") == "fix":
        cited = f"{match.group('scope') or ''} {message}"
        if _FIX_REFERENCE.search(cited) is None:
            found.append(
                "a `fix:` cites no BUG/BOT/EPIC/PRO id, case study or `PR #n` review "
                "(fix-bug-rule.md §6)"
            )
    return found


def commits_in(revision_range: str) -> list[Commit]:
    """The non-merge commits of `revision_range` (`base..head`), oldest first."""
    git = shutil.which("git")
    if git is None:
        raise FileNotFoundError("git is not on PATH")
    output = subprocess.run(  # noqa: S603 -- `git` is an absolute path resolved above
        [
            git,
            "log",
            "--no-merges",
            "--reverse",
            "--format=%H%x00%B%x1e",
            revision_range,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    commits: list[Commit] = []
    for record in output.split(_RECORD_SEPARATOR):
        record = record.strip("\n")
        if record:
            sha, _, message = record.partition(_FIELD_SEPARATOR)
            commits.append(Commit(sha, message))
    return commits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("revision_range", help="the commits to check, as `base..head`")
    arguments = parser.parse_args(argv)
    commits = commits_in(arguments.revision_range)
    failures = 0
    for commit in commits:
        for problem in problems(commit.message):
            failures += 1
            print(f"{commit.sha[:12]}: {problem}")
    if failures:
        print(f"\n{failures} problem(s) in {len(commits)} commit(s).", file=sys.stderr)
        return 1
    print(f"OK: {len(commits)} commit(s) follow commit-rule.md §2.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
