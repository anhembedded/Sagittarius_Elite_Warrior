"""Measure the process, not only the app — the baseline the strategic review of 2026-09-16 set.

Prints one row per measure with the value read from the tree right now. Used by the
process-drift audit (`.claude/skills/process-drift/SKILL.md`) and at each epic
retrospective. Everything here is a filesystem count; the git-derived measures (share of
commits by one session, commits that only record other commits) are one `git log` each and
are left to the audit prompt so this script needs nothing but the tree.

Usage:
    python3 scripts/measure_process.py
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.scripts.render_claude_manifest import front_matter

#: The text an agent reads before a change to `src/`: the entry point, the map, and the
#: rules that load for a source file or before a commit.
MUST_READ_FOR_SRC: tuple[str, ...] = (
    "CLAUDE.md",
    ".claude/ONBOARDING.md",
    ".claude/rules/architecture-rule.md",
    ".claude/rules/code-quality-rule.md",
    ".claude/rules/ci-rule.md",
    ".claude/rules/commit-rule.md",
    ".claude/rules/testing-rule.md",
    ".claude/rules/logging-rule.md",
)


def repo_root() -> Path:
    """The repository root, found by landmark rather than by hop count."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("pyproject.toml not found above this script")


def line_count(paths: list[Path]) -> int:
    return sum(len(p.read_text(encoding="utf-8").splitlines()) for p in paths)


def measures(root: Path) -> list[tuple[str, int]]:
    """(measure, value) pairs, in the order the report prints them."""
    claude = root / ".claude"
    rules = sorted((claude / "rules").rglob("*.md"))
    scoped = [rule for rule in rules if front_matter(rule).get("paths")]
    always = [root / "CLAUDE.md", claude / "ONBOARDING.md"] + [
        rule for rule in rules if rule not in scoped
    ]
    process_text = (
        [root / "CLAUDE.md"]
        + sorted(claude.glob("*.md"))
        + rules
        + sorted((claude / "skills").glob("*/SKILL.md"))
        + sorted((claude / "agents").glob("*.md"))
        + sorted((claude / "templates").glob("*.md"))
    )
    architecture = root / "tests" / "unit" / "architecture"
    allowlist = architecture / "allowlist_module_boundaries.txt"
    allowlist_entries = [
        line
        for line in allowlist.read_text(encoding="utf-8").splitlines()
        if line and line[0].islower()
    ]
    tasks = root / "Tasks"
    return [
        ("rule files", len(rules)),
        ("rule lines", line_count(rules)),
        (
            "lines read before a src/ change",
            line_count([root / p for p in MUST_READ_FOR_SRC]),
        ),
        ("process text lines (CLAUDE.md, .claude)", line_count(process_text)),
        ("lines loaded every session", line_count(always)),
        ("rules loading by path", len(scoped)),
        (
            "guard files under tests/unit/architecture",
            len(list(architecture.glob("test_*.py"))),
        ),
        (
            "board and document guards at tests/unit",
            len(list((root / "tests" / "unit").glob("test_*.py"))),
        ),
        (
            "ratchet and baseline files",
            len(
                list(architecture.glob("baseline_*"))
                + list(architecture.glob("allowlist_*"))
            ),
        ),
        ("boundary allowlist entries", len(allowlist_entries)),
        ("case studies", len(list((root / "Docs" / "CASE_STUDIES").glob("CS-*.md")))),
        (
            "open bug reports",
            len(list((tasks / "bug_report" / "incomplete").glob("*.md"))),
        ),
        (
            "closed bug reports",
            len(list((tasks / "bug_report" / "completed").glob("*.md"))),
        ),
        ("tasks completed", len(list((tasks / "completed").glob("*.md")))),
        ("tasks in backlog", len(list((tasks / "backlog").glob("*.md")))),
        ("skills", len(list((claude / "skills").glob("*/SKILL.md")))),
        ("subagents", len(list((claude / "agents").glob("*.md")))),
        ("templates", len(list((claude / "templates").glob("*.md")))),
    ]


def main() -> int:
    for name, value in measures(repo_root()):
        print(f"{name}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
