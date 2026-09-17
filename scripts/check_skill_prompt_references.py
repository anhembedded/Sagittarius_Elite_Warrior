"""Fail when a rule, skill, agent, template or map under `.claude/` names a repository path that is gone.

Every document under `.claude/` is read by a session that follows its links without
doubting them -- a scheduled audit, a reviewer working from the checklist, a fresh
session reading the map. Such a reader cannot notice that the document has gone
stale: it keeps hunting for what the repository deleted, keeps citing a rule file that
never existed, and keeps reporting success. That is not hypothetical here -- a
scheduled agent's briefing spent months telling it to read a rule file with no commit
in any branch's history, and four briefings told their agent to re-read a journal that
had never been written (`EPIC-011` is the record).

This checker is the mechanical half of `.claude/ONBOARDING.md` §13's rule "a path is
checked before it is cited". It cannot tell that a *claim* went stale -- only a human
or a run can -- but it does catch the class of rot that has actually shipped: a
document pointing at something that is not there. `CLAUDE.md` at the root is read the
same way, so it is checked too.

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

@par Why it also checks section anchors (2026-09-17)
A cited *section* rots the same way a cited path does, and faster: the rule
rewrite of 2026-09-17 renumbered `ci-rule.md` and `report-rule.md`, and five
documents kept pointing at `ci-rule.md` §3a, `ci-rule.md` §6, `report-rule.md`
§7 and `ONBOARDING.md` §12.5 -- sections that no longer exist. Every one passed
this checker, because the *file* was still there. A reader following
`ONBOARDING.md` §12.5 finds four items and invents the fifth. So a `§N`
citation naming a document under `.claude/` is resolved to a real heading, or to
a real numbered item inside the heading it subdivides (`ONBOARDING.md` §12.3 is
item 3 of section 12), and fails here otherwise.

Run it before committing any edit under any of `PROMPT_TREES` below:

    python3 scripts/check_skill_prompt_references.py

Exit code 0 = every referenced path and section resolves; 1 = at least one does not.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath

#: The document trees this checker reads, as (directory, glob) pairs relative to
#: the repository root. A tree is listed here because a reader follows its links
#: without verifying them; the glob is recursive where the tree nests. Every tree
#: must exist and hold at least one file, or the checker fails rather than passing
#: on an empty scan -- the same rule `tests/unit/architecture/scanned_roots_registry.py`
#: applies to the pytest guards, which cannot cover this script because it is not
#: a test.
PROMPT_TREES: tuple[tuple[Path, str], ...] = (
    (Path("."), "CLAUDE.md"),
    (Path(".claude"), "*.md"),
    (Path(".claude") / "rules", "**/*.md"),
    (Path(".claude") / "skills", "**/*.md"),
    (Path(".claude") / "agents", "*.md"),
    (Path(".claude") / "templates", "*.md"),
)

#: Repository-root directories this checker claims authority over. A reference
#: is only verified when it starts with one of these, which is what lets the
#: prompts keep talking about `package.json` (to say the repo has none) and
#: about `sagittarius_engine/` (a separate repository, not on this disk)
#: without either being reported as missing. Extending this list is a
#: deliberate act: every entry means "a path under here is expected to exist in
#: this checkout".
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

#: A section citation is written as a document followed by `§N` on the same
#: line -- ``\`ci-rule.md\` §2a``, ``\`.claude/ONBOARDING.md\` §7``,
#: ``ONBOARDING §12.3``. The two alternatives are matched by one pattern so a
#: single left-to-right pass can bind each anchor to the document named just
#: before it (within `_ANCHOR_REACH`), which is how the prompts are actually
#: written ("Follow ONBOARDING §6 for standalone tasks and §12.3 for epic
#: children").
_SECTION_CITATION = re.compile(
    r"`([^`\n]*?\.md)`|\b(CLAUDE|ONBOARDING|CONSTITUTION)\b|§\s?(\d+(?:\.\d+)*[a-z]?)"
)

#: A numbered heading, as every checked document writes them: `## 7. Authority`,
#: `### 2.1 Contracts are explicit`, `### 2a. tests/testnet/`, `## 6.5 Case study`.
_NUMBERED_HEADING = re.compile(
    r"^(#{2,6})\s+(\d+(?:\.\d+)*[a-z]?)[.)]?\s", re.MULTILINE
)

#: An ordered-list item inside a section body: `ONBOARDING.md` §12.3 names item
#: 3 of section 12, not a heading of its own.
_ORDERED_ITEM = re.compile(r"^\s*(\d+)\.\s", re.MULTILINE)

#: How far after a document's name a `§N` may still name that document's
#: section. A citation is written tight -- ``\`ci-rule.md\` §2a`` -- while a
#: line that names a rule and then says `§4` of a *task* (`Tasks/ROADMAP.md`
#: does exactly that about `BOT-087`) means something else entirely. Binding by
#: proximity keeps that out: a guard that cries wolf gets switched off.
_ANCHOR_REACH = 30

#: Bare document names the prompts use without their extension.
_BARE_DOCUMENTS = {
    "CLAUDE": "CLAUDE.md",
    "ONBOARDING": ".claude/ONBOARDING.md",
    "CONSTITUTION": ".claude/CONSTITUTION.md",
}


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

    A link is written relative to the file that carries it -- `.claude/ONBOARDING.md`
    from the root `CLAUDE.md`, `../../../.claude/rules/ci-rule.md` from
    `.claude/skills/pr-review/` -- so it is resolved against `source.parent`,
    not against any fixed base, before being compared with `CHECKED_ROOTS`.
    That is what lets one function serve trees at different depths.
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


def _resolve_document(name: str, source: Path, root: Path) -> Path | None:
    """The checked document `name` refers to, or `None` when it is not one.

    Only documents inside `PROMPT_TREES` are resolved: their section numbering
    is what a session navigates. A name carrying a slash is repository-relative;
    a bare `ci-rule.md` is looked for beside the citing file first, then in the
    trees that hold the rules and the map.
    """
    if "/" in name:
        candidates = [root / name.lstrip("./")]
    else:
        candidates = [
            source.parent / name,
            root / ".claude" / "rules" / name,
            root / ".claude" / name,
            root / name,
        ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if not resolved.is_file():
            continue
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError:
            return None
        if relative == "CLAUDE.md" or relative.startswith(".claude/"):
            return resolved
    return None


def _sections(document: Path) -> tuple[set[str], dict[str, set[str]]]:
    """Every numbered heading in `document`, and the ordered items under each.

    @return (heading numbers, {heading number: item numbers directly beneath it}).
    """
    text = document.read_text(encoding="utf-8")
    headings = [
        (match.group(2), match.start(), len(match.group(1)))
        for match in _NUMBERED_HEADING.finditer(text)
    ]
    numbers = {number for number, _, _ in headings}
    items: dict[str, set[str]] = {}
    for index, (number, start, depth) in enumerate(headings):
        end = len(text)
        for later_number, later_start, later_depth in headings[index + 1 :]:
            del later_number
            if later_depth <= depth:
                end = later_start
                break
        items[number] = set(_ORDERED_ITEM.findall(text[start:end]))
    return numbers, items


def _anchor_resolves(anchor: str, document: Path) -> bool:
    """Whether `document` holds the section `anchor` names."""
    numbers, items = _sections(document)
    if anchor in numbers:
        return True
    parent, _, item = anchor.rpartition(".")
    return bool(parent) and parent in numbers and item in items.get(parent, set())


def _dangling_anchors(source: Path, text: str, root: Path) -> list[str]:
    """Every `§N` in `source` whose document has no such section."""
    dangling: list[str] = []
    for line in text.splitlines():
        document: Path | None = None
        named_at = 0
        for match in _SECTION_CITATION.finditer(line):
            backticked, bare, anchor = match.groups()
            if backticked or bare:
                name = backticked or _BARE_DOCUMENTS[bare]
                document = _resolve_document(name, source, root)
                named_at = match.end()
                continue
            if anchor is None or document is None:
                continue
            if match.start() - named_at > _ANCHOR_REACH:
                document = None  # Too far away to be that document's section.
                continue
            if not _anchor_resolves(anchor, document):
                dangling.append(f"{document.relative_to(root).as_posix()} §{anchor}")
            named_at = match.end()
    return dangling


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


def check_anchors(root: Path) -> list[tuple[Path, str]]:
    """Return every (source file, dangling `document §N`) pair across `PROMPT_TREES`."""
    dangling: list[tuple[Path, str]] = []
    for source in _prompt_files(root):
        text = source.read_text(encoding="utf-8")
        for citation in dict.fromkeys(_dangling_anchors(source, text, root)):
            dangling.append((source.relative_to(root), citation))
    return dangling


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
            "reads as a pattern\n(`.claude/skills/<name>/SKILL.md`) or inside a command, "
            "not as a bare literal path.",
            file=sys.stderr,
        )
        return 1

    dangling = check_anchors(root)
    if dangling:
        print("Dangling section citations:\n", file=sys.stderr)
        for source, citation in dangling:
            print(f"  {source}: {citation}", file=sys.stderr)
        print(
            "\nA cited section must exist as a numbered heading, or as a numbered "
            "item directly\nunder the heading it subdivides. Renumbering a rule "
            "means repointing what cites it.",
            file=sys.stderr,
        )
        return 1

    trees = ", ".join(d.as_posix() + "/" for d, _ in PROMPT_TREES)
    print(
        f"OK: every repository path and section referenced by {len(_prompt_files(root))} "
        f"document(s) under {trees} resolves."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
