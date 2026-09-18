"""Mechanical validator for skills in .claude/skills/.

Enforces Constitutional invariants, frontmatter schema, anchor subordinations,
and path resolution across repository skills.

Usage:
    python scripts/validate_skill.py [skill-name]
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

_FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_SYSTEM_PROMPT_RE = re.compile(r"^# SYSTEM PROMPT:\s+(.+)$", re.MULTILINE)
_CONSTITUTION_REF = ".claude/CONSTITUTION.md"

#: `frontmatter.description` below this many characters reads as a stub, not
#: a real one-line summary.
_MIN_DESCRIPTION_LENGTH = 20
#: A `SKILL.md` under this many lines has not said enough to be a skill.
_MIN_SKILL_LINES = 15
#: Past this many lines a skill should modularize into `references/`.
_MAX_SKILL_LINES = 150


def repo_root() -> Path:
    """Find repository root by locating pyproject.toml."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("pyproject.toml not found above this script")


def parse_frontmatter(text: str) -> dict[str, str]:
    """Extract simple key-value YAML frontmatter."""
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        return {}
    fields = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        fields[key.strip()] = val.strip()
    return fields


def validate_skill(skill_dir: Path, tracked_files: set[str]) -> list[str]:
    """Validate a single skill directory against architectural invariants."""
    findings: list[str] = []
    name = skill_dir.name
    skill_file = skill_dir / "SKILL.md"

    if not skill_file.is_file():
        return [f"{name}: missing SKILL.md"]

    text = skill_file.read_text(encoding="utf-8")
    lines = text.splitlines()

    # 1. Frontmatter
    fields = parse_frontmatter(text)
    if not fields:
        findings.append(f"{name}/SKILL.md: missing or malformed YAML frontmatter")
    else:
        declared_name = fields.get("name", "")
        if declared_name != name:
            findings.append(
                f"{name}/SKILL.md: frontmatter name '{declared_name}' does not match directory '{name}'"
            )
        desc = fields.get("description", "")
        if not desc or len(desc) < _MIN_DESCRIPTION_LENGTH:
            findings.append(
                f"{name}/SKILL.md: description is missing or too short "
                f"(minimum {_MIN_DESCRIPTION_LENGTH} chars)"
            )

    # 2. System Prompt Heading
    sp_match = _SYSTEM_PROMPT_RE.search(text)
    if not sp_match:
        findings.append(f"{name}/SKILL.md: missing '# SYSTEM PROMPT: <ROLE>' heading")

    # 3. Constitutional Anchor
    if _CONSTITUTION_REF not in text:
        findings.append(
            f"{name}/SKILL.md: missing explicit citation of {_CONSTITUTION_REF}"
        )
    if not any(
        term in text.lower()
        for term in ("subordinated", "constitutional invariant", "constitution")
    ):
        findings.append(f"{name}/SKILL.md: missing Constitutional subordination clause")

    # 4. Modularity & Non-Redundancy
    # Flag if the skill attempts to re-explain the 5-step loop definitions instead of referencing
    if "Option A (The Duct-Tape" in text or "Option C (The Autonomous" in text:
        findings.append(
            f"{name}/SKILL.md: contains redundant copy-pasted 5-step option prose; cite CONSTITUTION.md instead"
        )

    # 5. Density & Length Sanity
    if len(lines) < _MIN_SKILL_LINES:
        findings.append(
            f"{name}/SKILL.md: vacuous skill file (<{_MIN_SKILL_LINES} lines)"
        )
    if len(lines) > _MAX_SKILL_LINES:
        findings.append(
            f"{name}/SKILL.md: excessive length ({len(lines)} lines, "
            f"max {_MAX_SKILL_LINES}). Modularize into references/"
        )

    return findings


def get_tracked_files(root: Path) -> set[str]:
    """Retrieve git tracked files to verify references."""
    git = shutil.which("git")
    if git is None:
        return set()
    try:
        # `S603` is suppressed, not worked around: the argument vector is this
        # literal list plus `root`, which is this checkout's own path, there
        # is no shell, and `git` is an absolute path resolved above rather
        # than a name looked up at spawn time.
        res = subprocess.run(  # noqa: S603
            [git, "-C", str(root), "ls-files"],
            capture_output=True,
            text=True,
            check=True,
        )
        return set(res.stdout.splitlines())
    except (OSError, subprocess.CalledProcessError):
        return set()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate repository skills")
    parser.add_argument(
        "skill_name",
        nargs="?",
        help="Optional skill directory name to validate. If omitted, all skills are validated.",
    )
    args = parser.parse_args()

    root = repo_root()
    skills_dir = root / ".claude" / "skills"
    tracked = get_tracked_files(root)

    if args.skill_name:
        target_dir = skills_dir / args.skill_name
        if not target_dir.is_dir():
            print(f"Error: skill directory not found: {target_dir}", file=sys.stderr)
            return 1
        targets = [target_dir]
    else:
        targets = sorted([d for d in skills_dir.iterdir() if d.is_dir()])

    all_findings: list[str] = []
    for skill_dir in targets:
        findings = validate_skill(skill_dir, tracked)
        all_findings.extend(findings)

    if all_findings:
        print(
            f"FAILED: {len(all_findings)} skill validation finding(s):", file=sys.stderr
        )
        for f in all_findings:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"OK: verified {len(targets)} skill(s) against architectural invariants.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
