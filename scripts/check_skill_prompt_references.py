"""Fail when an agent briefing, skill or rule pointer names a repository path that is gone.

The seven agents under `.agents/Skills/` run unattended on a schedule. An agent
cannot notice that its own briefing has gone stale: it will keep hunting for
what the repository deleted, keep citing a rule file that never existed, and
keep reporting success. That is not hypothetical here -- `sentinel.prompt.md`
spent months telling its agent to read `.agents/rules/sentinel-rule.md`, a file
with no commit in any branch's history, and four prompts told their agent to
re-read a journal that had never been written.

This checker is the mechanical half of the `.agents/Skills/README.md` rule
"verify, don't restate". It cannot tell that a *claim* went stale -- only a
human or a run can -- but it does catch the class of rot that has actually
shipped: a document pointing at something that is not there.

@par Why `.claude/` is checked too (added 2026-09-15, review finding S3)
It originally read `.agents/Skills/` alone. But `.claude/skills/` and
`.claude/rules/` hold exactly the same kind of document and are loaded by
exactly the same mechanism of trust -- a reader follows their links without
doubting them. `.claude/skills/pr-review/SKILL.md` is the sharpest case: it is
the checklist a reviewer works from, it names a dozen rule files and about
sixteen repository paths by link or backtick, and nothing verified any of them.
Every one resolved when the review checked by hand, which is a state and not a
guarantee: the first rename under `.agents/rules/` or `tests/unit/architecture/`
would have sent the next reviewer to a file that no longer exists, with no
reason to doubt it. Same rot, same fix -- `EPIC-011` is the record of it
happening once already.

@par Why it asks git and not the filesystem (`BUG-129`, 2026-09-17)
It resolved every reference with `Path.exists()` until then, which answers about
the disk it runs on rather than about the repository. A working tree carries
more than the repository does: `EPIC-025`'s moves left `src/domain/backtesting/`
and `src/application/use_cases/` behind as directories holding nothing but
`__pycache__`, and nothing deletes those. So two prompts citing those paths
passed here on every developer machine and failed in GitHub CI, which clones
fresh -- and because this step runs before the tests, every later step was
skipped: `master-warrior` was red for three merges while the local gate called
that step green. A checker whose answer depends on who runs it is worse than no
checker, because it is believed. It reads `git ls-files` now, so local and CI
answer the same question: is this path in the repository?

Run it before committing any edit under any of `PROMPT_TREES` below:

    python3 scripts/check_skill_prompt_references.py

Exit code 0 = every referenced path resolves; 1 = at least one does not.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath

#: The document trees this checker reads, as (directory, glob) pairs relative to
#: the repository root. A tree is listed here because a reader follows its links
#: without verifying them; the glob is recursive where the tree nests one
#: directory per skill. All three must exist and hold at least one file, or the
#: checker fails rather than passing on an empty scan -- the same rule
#: `tests/unit/architecture/scanned_roots_registry.py` applies to the pytest
#: guards, which cannot cover this script because it is not a test.
PROMPT_TREES: tuple[tuple[Path, str], ...] = (
    (Path(".agents") / "Skills", "*.md"),
    (Path(".claude") / "skills", "**/*.md"),
    (Path(".claude") / "rules", "*.md"),
)

#: Repository-root directories this checker claims authority over. A reference
#: is only verified when it starts with one of these, which is what lets the
#: prompts keep talking about `package.json` (to say the repo has none) and
#: about `sagittarius_engine/` (a separate repository, not on this disk)
#: without either being reported as missing. Extending this list is a
#: deliberate act: every entry means "a path under here is expected to exist in
#: this checkout".
CHECKED_ROOTS = (
    ".agents/",
    ".claude/",
    ".github/",
    "Docs/",
    "Tasks/",
    "scripts/",
    "src/",
    "tests/",
)

#: Characters that mean the backticked span is a shell command, a glob, or a
#: placeholder such as `.agents/Skills/<agent>.md` -- never a literal path to
#: verify.
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

    A link is written relative to the file that carries it -- `../../CLAUDE.md`
    from `.agents/Skills/`, `../../../.agents/rules/ci-rule.md` from
    `.claude/skills/pr-review/` -- so it is resolved against `source.parent`,
    not against any fixed base, before being compared with `CHECKED_ROOTS`.
    That is what lets one function serve trees at three different depths.
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


def _prompt_files(root: Path) -> list[Path]:
    """Every document in every tree, deduplicated and in a stable order."""
    found: dict[Path, None] = {}
    for directory, glob in PROMPT_TREES:
        for source in sorted((root / directory).glob(glob)):
            found.setdefault(source, None)
    return list(found)


def _tracked_paths(root: Path) -> set[str] | None:
    """Every path the repository holds, or `None` when git cannot answer.

    @details `git ls-files` lists **files**, and the briefings cite directories
    too, so every ancestor of every tracked file is added: `src/kept/module.py`
    also registers `src/kept` and `src` as things that exist. The index is read
    rather than a commit, because a move that has been staged but not yet
    committed is real work and this checker runs before that commit.

    Returns `None` rather than an empty set when git is unavailable or `root` is
    not a repository. An empty set would read as "the repository holds nothing"
    and fail every reference; `None` says "no answer", which the caller handles
    by falling back to the filesystem **and saying so**.
    """
    git = shutil.which("git")
    if git is None:
        return None
    try:
        # `S603` is suppressed, not worked around: the argument vector is this
        # literal list plus `root`, which is this checkout's own path, there is
        # no shell, and `git` is an absolute path resolved above rather than a
        # name looked up at spawn time.
        completed = subprocess.run(  # noqa: S603
            [git, "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    tracked: set[str] = set()
    for entry in completed.stdout.split("\0"):
        if not entry:
            continue
        tracked.add(entry)
        parent = PurePosixPath(entry).parent
        while parent != PurePosixPath("."):
            tracked.add(parent.as_posix())
            parent = parent.parent
    return tracked


def _resolves(reference: str, tracked: set[str] | None, root: Path) -> bool:
    """Whether the repository holds `reference`.

    A cited directory may or may not carry a trailing slash — the briefings are
    written both ways — so it is stripped before the lookup.
    """
    if tracked is None:
        return (root / reference).exists()
    return reference.rstrip("/") in tracked


def check(root: Path) -> list[tuple[Path, str]]:
    """Return every (source file, missing path) pair across `PROMPT_TREES`."""
    tracked = _tracked_paths(root)
    if tracked is None:
        print(
            "warning: git could not list this tree, so paths are being checked "
            "against the working directory. An untracked leftover will read as "
            "present here and missing in CI (`BUG-129`).",
            file=sys.stderr,
        )
    missing: list[tuple[Path, str]] = []
    for source in _prompt_files(root):
        text = source.read_text(encoding="utf-8")
        references = _backticked_references(text) + _link_references(text, source, root)
        # A document naturally names the same path more than once; report once.
        for reference in dict.fromkeys(references):
            if not _resolves(reference, tracked, root):
                missing.append((source.relative_to(root), reference))
    return missing


def _empty_trees(root: Path) -> list[str]:
    """Trees that are missing, or present but holding nothing to check.

    A checker that passes because it read no files is the failure mode this
    exists to prevent, so an empty tree is an error and not a quiet skip.
    """
    empty: list[str] = []
    for directory, glob in PROMPT_TREES:
        path = root / directory
        if not path.is_dir():
            empty.append(f"{directory.as_posix()}/ does not exist")
        elif not any(path.glob(glob)):
            empty.append(f"{directory.as_posix()}/ holds no {glob}")
    return empty


def main() -> int:
    root = _repo_root()
    problems = _empty_trees(root)
    if problems:
        print("error: a checked document tree is empty:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nEither the tree moved -- retarget PROMPT_TREES in this file -- or "
            "it was deleted.\nPassing on an empty scan is what this check exists "
            "to prevent.",
            file=sys.stderr,
        )
        return 1

    missing = check(root)
    if missing:
        trees = ", ".join(d.as_posix() + "/" for d, _ in PROMPT_TREES)
        print(f"Broken references in {trees}:\n", file=sys.stderr)
        for source, reference in missing:
            print(f"  {source}: {reference}", file=sys.stderr)
        print(
            "\nEvery backticked path under "
            f"{'/, '.join(root_dir.rstrip('/') for root_dir in CHECKED_ROOTS)}/ "
            "must exist.\nIf the path is deliberately absent here, write it so it "
            "reads as a pattern\n(`.agents/Skills/<agent>.md`) or inside a command, "
            "not as a bare literal path.",
            file=sys.stderr,
        )
        return 1

    trees = ", ".join(d.as_posix() + "/" for d, _ in PROMPT_TREES)
    print(
        f"OK: every repository path referenced by {len(_prompt_files(root))} "
        f"document(s) under {trees} resolves."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
