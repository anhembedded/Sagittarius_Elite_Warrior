"""Fail when a `.jules/*.md` prompt points at a repository path that is gone.

The seven agents under `.jules/` run unattended on a schedule. An agent cannot
notice that its own briefing has gone stale: it will keep hunting for what the
repository deleted, keep citing a rule file that never existed, and keep
reporting success. That is not hypothetical here -- `sentinel.prompt.md` spent
months telling its agent to read `.agents/rules/sentinel-rule.md`, a file with
no commit in any branch's history, and four prompts told their agent to re-read
a journal that had never been written.

This checker is the mechanical half of the `.jules/README.md` rule "verify,
don't restate". It cannot tell that a *claim* went stale -- only a human or a
run can -- but it does catch the class of rot that has actually shipped: a
prompt pointing at something that is not there.

Run it before committing any edit under `.jules/`:

    python3 scripts/check_jules_prompt_references.py

Exit code 0 = every referenced path resolves; 1 = at least one does not.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

#: Repository-root directories this checker claims authority over. A reference
#: is only verified when it starts with one of these, which is what lets the
#: prompts keep talking about `package.json` (to say the repo has none) and
#: about `sagittarius_engine/` (a separate repository, not on this disk)
#: without either being reported as missing. Extending this list is a
#: deliberate act: every entry means "a path under here is expected to exist in
#: this checkout".
CHECKED_ROOTS = (
    ".agents/",
    ".github/",
    ".jules/",
    "Docs/",
    "Tasks/",
    "scripts/",
    "src/",
    "tests/",
)

#: Characters that mean the backticked span is a shell command, a glob, or a
#: placeholder such as `.jules/<agent>.md` -- never a literal path to verify.
_NOT_A_LITERAL_PATH = re.compile(r"""[\s*?<>|$"'()\[\]{}]|::|https?:""")

_BACKTICKED = re.compile(r"`([^`\n]+)`")
_MARKDOWN_LINK = re.compile(r"\[[^\]\n]*\]\(([^)\n]+)\)")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _is_verifiable(candidate: str) -> bool:
    """True when `candidate` claims a path this checkout must contain."""
    if _NOT_A_LITERAL_PATH.search(candidate):
        return False
    return candidate.startswith(CHECKED_ROOTS)


def _backticked_references(text: str) -> list[str]:
    return [span for span in _BACKTICKED.findall(text) if _is_verifiable(span)]


def _link_references(text: str, source: Path, root: Path) -> list[str]:
    """Markdown link targets, normalised to repository-relative form.

    Links in these prompts are written relative to `.jules/`, so `../CLAUDE.md`
    has to be resolved against the source file before it can be compared with
    `CHECKED_ROOTS`.
    """
    references: list[str] = []
    for target in _MARKDOWN_LINK.findall(text):
        target = target.split("#", 1)[0].strip()
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


def check(root: Path) -> list[tuple[Path, str]]:
    """Return every (prompt file, missing path) pair found under `.jules/`."""
    missing: list[tuple[Path, str]] = []
    for source in sorted((root / ".jules").glob("*.md")):
        text = source.read_text(encoding="utf-8")
        references = _backticked_references(text) + _link_references(text, source, root)
        # A prompt naturally names the same path more than once; report it once.
        for reference in dict.fromkeys(references):
            if not (root / reference).exists():
                missing.append((source.relative_to(root), reference))
    return missing


def main() -> int:
    root = _repo_root()
    jules = root / ".jules"
    if not jules.is_dir():
        print(f"error: {jules} does not exist", file=sys.stderr)
        return 1

    missing = check(root)
    if missing:
        print("Broken references in .jules/ prompts:\n", file=sys.stderr)
        for source, reference in missing:
            print(f"  {source}: {reference}", file=sys.stderr)
        print(
            "\nEvery backticked path under "
            f"{'/, '.join(root_dir.rstrip('/') for root_dir in CHECKED_ROOTS)}/ "
            "must exist.\nIf the path is deliberately absent here, write it so it "
            "reads as a pattern\n(`.jules/<agent>.md`) or inside a command, not as "
            "a bare literal path.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: every repository path referenced by {jules.name}/*.md resolves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
