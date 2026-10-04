"""Which documents each check reads, as (directory, glob) pairs relative to the root.

A tree is listed here because a reader follows its links without verifying them;
the glob is recursive where the tree nests. Every tree must exist and hold at
least one file, or the CLI fails rather than passing on an empty scan -- the
same rule `tests/unit/architecture/scanned_roots_registry.py` applies to the
pytest guards.
"""

from __future__ import annotations

from pathlib import Path

Tree = tuple[Path, str]

_CLAUDE = Path(".claude")

#: Every prompt document: path references and tag grammar are checked here.
PROMPT_TREES: tuple[Tree, ...] = (
    (Path("."), "CLAUDE.md"),
    (_CLAUDE, "*.md"),
    (_CLAUDE / "rules", "**/*.md"),
    (_CLAUDE / "skills", "**/*.md"),
    (_CLAUDE / "agents", "*.md"),
    (_CLAUDE / "templates", "*.md"),
)

#: Where a `§` citation can be written: the prompts, plus the two machine-read
#: files that cite rule sections in prose (the CI workflow, the skill contracts).
CITATION_TREES: tuple[Tree, ...] = (
    *PROMPT_TREES,
    (Path(".github") / "workflows", "*.yml"),
    (_CLAUDE / "skills", "**/contract.json"),
)

#: The rule files whose every clause names the mechanism enforcing it.
#: `pitfalls/` is a list of traps, not of obligations, so it carries no tags.
RULE_TREES: tuple[Tree, ...] = ((_CLAUDE / "rules", "**/*.md"),)
RULE_EXCLUDED: tuple[Path, ...] = (_CLAUDE / "rules" / "pitfalls",)

#: The documents that state rules and must not narrate how they came to be:
#: history belongs in a `DECISION_*.md`, which a rule can cite.
HISTORY_FREE_TREES: tuple[Tree, ...] = (
    *RULE_TREES,
    (_CLAUDE, "ONBOARDING.md"),
    (_CLAUDE, "CONSTITUTION.md"),
    (Path("."), "CLAUDE.md"),
)


def collect(
    root: Path, trees: tuple[Tree, ...], excluded: tuple[Path, ...] = ()
) -> list[Path]:
    """Every file in every tree, absolute, deduplicated and in a stable order."""
    found: dict[Path, None] = {}
    for directory, glob in trees:
        for source in sorted((root / directory).glob(glob)):
            relative = source.relative_to(root)
            if source.is_file() and not any(
                relative.is_relative_to(skip) for skip in excluded
            ):
                found.setdefault(source, None)
    return list(found)


def rule_files(root: Path) -> list[Path]:
    return collect(root, RULE_TREES, RULE_EXCLUDED)


def history_free_files(root: Path) -> list[Path]:
    return collect(root, HISTORY_FREE_TREES, RULE_EXCLUDED)


def empty_trees(root: Path, trees: tuple[Tree, ...]) -> list[str]:
    """Trees that are missing, or present but holding nothing to check.

    A checker that passes because it read no files is the failure mode this
    exists to prevent, so an empty tree is an error and not a quiet skip.
    """
    empty: list[str] = []
    for directory, glob in dict.fromkeys(trees):
        path = root / directory
        if not path.is_dir():
            empty.append(f"{directory.as_posix()}/ does not exist")
        elif not any(path.glob(glob)):
            empty.append(f"{directory.as_posix()}/ holds no {glob}")
    return empty
