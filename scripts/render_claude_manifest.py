"""Render the manifest of `.claude/` from the tree — the inventory table `.claude/README.md` carries.

Every file under `.claude/` declares itself in its own front matter (`description`, and
`paths:` for a rule that loads by file); this script reads those declarations and prints one
table row per file, so the manifest is derived and never written by hand.
`tests/unit/architecture/test_claude_tree_is_wired.py` fails when the README's table differs
from this output — the same shape as `render_task_counts.py` and the board guard.

Usage:
    python3 scripts/render_claude_manifest.py            # the table, ready to paste
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

CLAUDE_DIR = ".claude"

#: The markers `.claude/README.md` keeps around the derived table.
BEGIN_MARK = "<!-- manifest:begin -->"
END_MARK = "<!-- manifest:end -->"

_FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


@dataclass(frozen=True)
class Entry:
    """One row of the manifest."""

    path: str  # relative to `.claude/`, or `settings.json`
    kind: str
    loads: str
    description: str


def repo_root() -> Path:
    """The repository root, found by landmark rather than by hop count."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("pyproject.toml not found above this script")


def front_matter(path: Path) -> dict[str, str | list[str]]:
    """The YAML-shaped front matter of a Markdown file, as scalars and string lists.

    Stdlib only, on purpose: this runs wherever the rules do, without a YAML library.
    Handles the two shapes the tree uses — `key: value` and `key:` followed by
    `  - item` lines — and nothing else; a rule with a more exotic front matter is a
    finding, not a parsing feature.
    """
    match = _FRONT_MATTER_RE.match(path.read_text(encoding="utf-8"))
    if match is None:
        return {}
    fields: dict[str, str | list[str]] = {}
    current_list: str | None = None
    for line in match.group(1).splitlines():
        item = re.match(r"^\s+-\s*(.+?)\s*$", line)
        if item and current_list is not None:
            items = fields[current_list]
            if isinstance(items, list):
                items.append(item.group(1).strip().strip("\"'"))
            continue
        scalar = re.match(r"^([A-Za-z_-]+):\s*(.*?)\s*$", line)
        if scalar is None:
            continue
        key, value = scalar.group(1), scalar.group(2)
        if value:
            fields[key] = value
            current_list = None
        else:
            fields[key] = []
            current_list = key
    return fields


def _description(path: Path) -> str:
    value = front_matter(path).get("description", "")
    return value if isinstance(value, str) else ""


def _rule_entries(claude: Path) -> list[Entry]:
    rules_dir = claude / "rules"
    entries = []
    for rule in sorted(
        rules_dir.rglob("*.md"), key=lambda p: (len(p.parts), p.as_posix())
    ):
        paths = front_matter(rule).get("paths")
        loads = (
            "every session" if not paths else ", ".join(f"`{glob}`" for glob in paths)
        )
        entries.append(
            Entry(
                rule.relative_to(claude).as_posix(), "rule", loads, _description(rule)
            )
        )
    return entries


def _skill_entries(claude: Path) -> list[Entry]:
    entries = []
    for skill in sorted((claude / "skills").glob("*/SKILL.md")):
        name = skill.parent.name
        entries.append(
            Entry(
                skill.relative_to(claude).as_posix(),
                "skill",
                f"`/{name}`, or Claude from its description",
                _description(skill),
            )
        )
    return entries


def _agent_entries(claude: Path) -> list[Entry]:
    entries = []
    for agent in sorted((claude / "agents").glob("*.md")):
        entries.append(
            Entry(
                agent.relative_to(claude).as_posix(),
                "agent",
                f"delegation, or `@{agent.stem} (agent)`",
                _description(agent),
            )
        )
    return entries


def _template_entries(claude: Path) -> list[Entry]:
    entries = []
    for template in sorted((claude / "templates").glob("*.md")):
        entries.append(
            Entry(
                template.relative_to(claude).as_posix(),
                "template",
                "on demand, copied",
                _description(template),
            )
        )
    return entries


def _settings_entry(claude: Path) -> list[Entry]:
    settings = claude / "settings.json"
    if not settings.is_file():
        return []
    data = json.loads(settings.read_text(encoding="utf-8"))
    allow = data.get("permissions", {}).get("allow", [])
    events = ", ".join(f"`{event}`" for event in data.get("hooks", {}))
    description = f"{len(allow)} permission rules"
    if events:
        description += f"; hooks on {events}"
    return [
        Entry("settings.json", "settings", "Claude Code, every session", description)
    ]


def inventory(root: Path) -> list[Entry]:
    """Every file under `.claude/` that a session can load, in manifest order."""
    claude = root / CLAUDE_DIR
    onboarding = claude / "ONBOARDING.md"
    entries = [
        Entry(
            "ONBOARDING.md",
            "map",
            "imported by `CLAUDE.md`, every session",
            _description(onboarding),
        )
    ]
    entries += _settings_entry(claude)
    entries += _rule_entries(claude)
    entries += _skill_entries(claude)
    entries += _agent_entries(claude)
    entries += _template_entries(claude)
    return entries


def render_table(entries: list[Entry]) -> str:
    """The Markdown table, exactly as `.claude/README.md` must carry it."""
    lines = ["| Path | Kind | Loads | What it is |", "| :--- | :--- | :--- | :--- |"]
    for entry in entries:
        description = entry.description.replace("|", "\\|")
        lines.append(
            f"| `{entry.path}` | {entry.kind} | {entry.loads} | {description} |"
        )
    return "\n".join(lines)


def manifest_block(readme_text: str) -> str | None:
    """The text between the markers in `.claude/README.md`, or None when a marker is missing."""
    begin = readme_text.find(BEGIN_MARK)
    end = readme_text.find(END_MARK)
    if begin < 0 or end < 0 or end < begin:
        return None
    return readme_text[begin + len(BEGIN_MARK) : end].strip()


def main() -> int:
    print(render_table(inventory(repo_root())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
