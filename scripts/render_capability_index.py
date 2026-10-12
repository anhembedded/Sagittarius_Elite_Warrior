"""Render the capability catalog from the `Capability:` blocks in module docstrings.

A *capability* is a shared mechanism a developer reuses instead of building a second one
(`Docs/VOCABULARY/README.md`). Each is declared where it lives, in the docstring of the
module (or package `__init__.py`) that provides it:

    Capability: Choose a trading pair, with favourites and recents
        Also: symbol picker, pair chooser, ticker selector
        Use: SymbolPickerOverlay, ISymbolPickerSource
        User: src/modules/bots/ui/bots_screen/new_bot_symbols.py
        Status: stable

This script reads those blocks with `ast` — nothing is imported, so it needs neither Qt nor
the Engine — and renders the table `.claude/rules/capabilities.md` carries between its
markers. The rule loads when a session opens UI or application code, which is the moment
it decides whether to build or reuse (`EPIC-037A`).
`tests/unit/architecture/test_every_support_package_is_in_the_catalog.py` fails when the
block differs from this output, when a marker is malformed, and when a claim in one is
false (the symbol is not defined there, the user does not import it).

Usage:
    python3 scripts/render_capability_index.py           # the table, ready to paste
    python3 scripts/render_capability_index.py --write   # rewrite the rule file's block
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# Run bare (`python3 scripts/render_capability_index.py`) nothing puts the checkout's parent
# on the path, and the sibling module is imported by its package name below — the name the
# guards and mypy resolve it by — so the parent of the repository root is added here.
sys.path.insert(
    0,
    str(
        next(
            p
            for p in Path(__file__).resolve().parents
            if (p / "pyproject.toml").is_file()
        ).parent
    ),
)

from Sagittarius_Elite_Warrior.scripts.render_claude_manifest import repo_root

#: Where markers are read, relative to the repository root. `src/shell` is here because the
#: composition root's own helpers (the instance lock, the configuration loader) are what a
#: new entry point reuses (`EPIC-038A`); `capabilities.md` already loads on `src/shell/**`.
CAPABILITY_ROOTS: tuple[str, ...] = ("src/support", "src/core", "src/shell")

#: The rule file that carries the generated table, and the markers around it.
RULE_FILE = ".claude/rules/capabilities.md"
BEGIN_MARK = "<!-- capabilities:begin -->"
END_MARK = "<!-- capabilities:end -->"

_HEAD = re.compile(r"^Capability:[ \t]*(?P<need>.*?)[ \t]*$")
#: A line that looks like a head but is not one: `Capabilty:`, `capability:`, `Capabilities:`.
_NEAR_MISS = re.compile(r"^\s*capab\w*[ \t]*:", re.IGNORECASE)
_FIELD = re.compile(r"^(?P<key>[A-Z][a-z]+):[ \t]*(?P<value>.*?)[ \t]*$")
_STATUS = re.compile(r"^(?:stable|deprecated -> (?P<replacement>[A-Za-z_]\w*))$")

_REQUIRED_FIELDS = ("Use", "User", "Status")
_KNOWN_FIELDS = (*_REQUIRED_FIELDS, "Also")
_STABLE = "stable"
_DEPRECATED = "deprecated"


@dataclass(frozen=True)
class Capability:
    """One row of the catalog."""

    need: str
    synonyms: tuple[str, ...]
    symbols: tuple[str, ...]
    user: str  # repo-relative path of one real current consumer
    status: str  # `stable` or `deprecated`
    replacement: str  # the symbol that replaces a deprecated one, else ""
    source: str  # repo-relative path of the file whose docstring holds the marker

    @property
    def where(self) -> str:
        """Where to import from: the file, or the package directory for `__init__.py`."""
        if self.source.endswith("/__init__.py"):
            return self.source.removesuffix("__init__.py")
        return self.source


@dataclass(frozen=True)
class Parsed:
    """What one docstring declared, and what in it was malformed."""

    capabilities: tuple[Capability, ...]
    problems: tuple[str, ...]


def _split_list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _build(
    source: str, need: str, fields: dict[str, str], problems: list[str]
) -> Capability | None:
    """The capability a block declares, or None after appending why it is malformed."""
    before = len(problems)
    label = f"{source}: Capability {need!r}"
    if not need:
        problems.append(f"{source}: a `Capability:` head with no need text")
    for key in _REQUIRED_FIELDS:
        if not fields.get(key):
            problems.append(f"{label}: missing field `{key}:`")
    symbols = _split_list(fields.get("Use", ""))
    for symbol in symbols:
        if not symbol.isidentifier():
            problems.append(f"{label}: `Use:` entry {symbol!r} is not a symbol name")
    user = fields.get("User", "")
    if user and not (user.startswith("src/") and user.endswith(".py")):
        problems.append(f"{label}: `User:` must be a repo-relative src/ .py path")
    status = _STATUS.match(fields.get("Status", ""))
    if fields.get("Status") and status is None:
        problems.append(
            f"{label}: `Status:` is `stable` or `deprecated -> Symbol`, "
            f"not {fields['Status']!r}"
        )
    if len(problems) > before or status is None:
        return None
    replacement = status.group("replacement") or ""
    return Capability(
        need=need,
        synonyms=_split_list(fields.get("Also", "")),
        symbols=symbols,
        user=user,
        status=_DEPRECATED if replacement else _STABLE,
        replacement=replacement,
        source=source,
    )


def _read_block(
    lines: Sequence[str], start: int, source: str, problems: list[str]
) -> tuple[dict[str, str], int]:
    """The `Key: value` fields under the head at `start`, and the index after the block."""
    fields: dict[str, str] = {}
    key = ""
    block_indent = -1
    index = start + 1
    while index < len(lines):
        line = lines[index]
        if not line.strip() or not line[0].isspace():
            break
        indent = len(line) - len(line.lstrip())
        block_indent = indent if block_indent < 0 else block_indent
        if indent > block_indent and key:
            fields[key] = f"{fields[key]} {line.strip()}".strip()
        else:
            match = _FIELD.match(line.strip())
            if match is None or match["key"] not in _KNOWN_FIELDS:
                problems.append(
                    f"{source}: unknown or malformed field line {line.strip()!r} "
                    f"(fields: {', '.join(_KNOWN_FIELDS)})"
                )
                key = ""
            elif match["key"] in fields:
                problems.append(f"{source}: field `{match['key']}:` given twice")
                key = ""
            else:
                key = match["key"]
                fields[key] = match["value"]
        index += 1
    return fields, index


def parse_docstring(source: str, docstring: str) -> Parsed:
    """Every `Capability:` block in `docstring`, and every malformed one.

    `source` is the repo-relative path of the file, only used to name where a problem is.
    A head with a near-miss spelling is a problem, not a silently skipped row.
    """
    lines = docstring.splitlines()
    capabilities: list[Capability] = []
    problems: list[str] = []
    index = 0
    while index < len(lines):
        head = _HEAD.match(lines[index])
        if head is None:
            if _NEAR_MISS.match(lines[index]):
                problems.append(
                    f"{source}: {lines[index].strip()!r} looks like a capability head; "
                    "the exact spelling, at column 0, is `Capability:`"
                )
            index += 1
            continue
        fields, next_index = _read_block(lines, index, source, problems)
        built = _build(source, head["need"], fields, problems)
        if built is not None:
            capabilities.append(built)
        index = next_index
    return Parsed(tuple(capabilities), tuple(problems))


def collect(root: Path) -> Parsed:
    """Every capability declared under `CAPABILITY_ROOTS`, ordered by where it lives."""
    capabilities: list[Capability] = []
    problems: list[str] = []
    for relative_root in CAPABILITY_ROOTS:
        scan_root = root / relative_root
        if not scan_root.is_dir():
            raise FileNotFoundError(
                f"{scan_root} does not exist — the tree moved; retarget CAPABILITY_ROOTS"
            )
        for path in sorted(scan_root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            docstring = ast.get_docstring(
                ast.parse(path.read_text(encoding="utf-8")), clean=True
            )
            if docstring is None:
                continue
            parsed = parse_docstring(path.relative_to(root).as_posix(), docstring)
            capabilities.extend(parsed.capabilities)
            problems.extend(parsed.problems)
    capabilities.sort(key=lambda c: (c.where, c.need))
    return Parsed(tuple(capabilities), tuple(problems))


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _row(capability: Capability) -> str:
    need = capability.need
    if capability.synonyms:
        need += f" (also: {', '.join(capability.synonyms)})"
    use = ", ".join(f"`{symbol}`" for symbol in capability.symbols)
    if capability.status == _DEPRECATED:
        use = f"~~{use}~~ → `{capability.replacement}`"
    return f"| {_cell(need)} | {use} | `{capability.where}` | `{capability.user}` |"


def render_table(capabilities: Sequence[Capability]) -> str:
    """The Markdown table, exactly as `.claude/rules/capabilities.md` must carry it."""
    lines = ["| Need | Use | Where | Used by |", "| :--- | :--- | :--- | :--- |"]
    lines.extend(_row(capability) for capability in capabilities)
    return "\n".join(lines)


def table_block(rule_text: str) -> str | None:
    """The text between the markers, or None when a marker is missing or misordered."""
    begin = rule_text.find(BEGIN_MARK)
    end = rule_text.find(END_MARK)
    if begin < 0 or end < begin:
        return None
    return rule_text[begin + len(BEGIN_MARK) : end].strip()


def with_table(rule_text: str, table: str) -> str:
    """`rule_text` with the block between the markers replaced by `table`."""
    begin = rule_text.find(BEGIN_MARK)
    end = rule_text.find(END_MARK)
    if begin < 0 or end < begin:
        raise ValueError(f"{RULE_FILE} lost its {BEGIN_MARK} / {END_MARK} markers")
    head = rule_text[: begin + len(BEGIN_MARK)]
    return f"{head}\n{table}\n{rule_text[end:]}"


def main(argv: Sequence[str]) -> int:
    root = repo_root()
    parsed = collect(root)
    if parsed.problems:
        sys.stderr.write("\n".join(parsed.problems) + "\n")
        return 1
    table = render_table(parsed.capabilities)
    if "--write" in argv:
        rule = root / RULE_FILE
        rule.write_text(
            with_table(rule.read_text(encoding="utf-8"), table), encoding="utf-8"
        )
    else:
        sys.stdout.write(table + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
