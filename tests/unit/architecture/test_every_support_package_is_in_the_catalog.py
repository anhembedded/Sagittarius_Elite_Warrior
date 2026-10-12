"""Guard: the capability catalog covers every support unit and tells the truth
(`EPIC-037A`, `.claude/rules/capabilities.md`).

**Why this exists.** Class A of the bug reports is "did not reuse": `BUG-155` built a
free-text symbol field beside `SymbolPickerOverlay`, `BUG-165` hand-built empty labels
beside `empty_page`. Nothing told the session what existed at the moment it decided. The
catalog does, and a catalog is only as good as the checks that keep it complete and true.

**What it enforces** (the parser and renderer are `scripts/render_capability_index.py`):

1. *Complete.* A **unit** is a directory at depth 1 or 2 under `src/support/`, except
   `contracts`, `adapters` and `assets`, which roll up into their parent (ports,
   implementations and icons of it). A file belongs to its nearest unit. A unit holding no
   `Capability:` block fails. This began as a shrink-only baseline (the walking skeleton
   had three entries); it emptied, the file was deleted, and the guard is a ban.
2. *Well formed.* Every block parses; a near-miss head (`Capabilty:`) is an error, not a
   dropped row.
3. *True.* Each `Use` symbol is defined (or re-exported) at the top level of the marked
   module; each `User` file exists, lies outside the capability's own directory and
   *imports* a `Use` symbol, read with `ast`, never as text. A `deprecated ->` replacement is
   another row's symbol.
4. *Paths exist.* Every `src/...` path the rule file names exists.
5. *No hand edit drifts.* The generated block equals the generator's output.
6. *Small.* The rule file stays under its ceiling and the catalog under a floor that catches
   a lost scan.

Stdlib only: no Qt, no Engine.

Retire when: the catalog is produced by a tool the platform ships (Claude Code indexing
reusable symbols for a session), or the `Capability:` convention is dropped from
`capabilities.md`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from Sagittarius_Elite_Warrior.scripts.render_capability_index import (
    RULE_FILE,
    Capability,
    collect,
    parse_docstring,
    render_table,
    table_block,
    with_table,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SUPPORT = "src/support"

#: Directories that roll up into their parent unit instead of being one.
_ROLLS_UP = frozenset({"contracts", "adapters", "assets", "__pycache__"})
_UNIT_DEPTH = 2

#: Ceiling for the rule file, in lines. The catalog loads on every UI or application file, so
#: it stays small; it may fall, never rise without the owner's decision.
_RULE_MAX_LINES = 120
#: Floors that catch a lost scan (the markers or the units vanishing), not churn.
_MIN_CAPABILITIES = 25
_MIN_UNITS = 10

_CATALOGUED_PATH = re.compile(r"`(src/[^`\s]+)`")


# --------------------------------------------------------------------------- #
# Pure helpers                                                                #
# --------------------------------------------------------------------------- #


def defined_names(source: str) -> set[str]:
    """The names a module binds at its top level: classes, functions, assignments,
    type aliases and imports (an `__init__.py` re-exports by importing)."""
    names: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            names.add(node.name.id)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom | ast.Import):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
    return names


def imported_names(source: str) -> set[str]:
    """The names `source` imports from elsewhere, as written at the source (`from m import X`
    gives `X`, not an alias). A word in a string or comment is not an import."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name.split(".")[-1] for a in node.names)
    return names


def unit_directories(support: Path) -> list[Path]:
    """Every directory at depth 1 or 2 under `support` that is a unit."""
    units: list[Path] = []
    frontier = [support]
    for _ in range(_UNIT_DEPTH):
        frontier = [
            child
            for parent in frontier
            for child in sorted(parent.iterdir())
            if child.is_dir() and child.name not in _ROLLS_UP
        ]
        units.extend(frontier)
    return units


def owning_unit(file: Path, units: set[Path]) -> Path | None:
    """The nearest ancestor directory of `file` that is a unit."""
    return next((p for p in file.parents if p in units), None)


# --------------------------------------------------------------------------- #
# The tree                                                                    #
# --------------------------------------------------------------------------- #


def _capabilities() -> tuple[Capability, ...]:
    return collect(_REPO_ROOT).capabilities


def _units() -> set[Path]:
    support = _REPO_ROOT / _SUPPORT
    if not support.is_dir():
        raise FileNotFoundError(f"{support} does not exist — retarget this guard")
    return set(unit_directories(support))


def _uncatalogued_units() -> list[str]:
    units = _units()
    covered = {
        owning_unit(_REPO_ROOT / capability.source, units)
        for capability in _capabilities()
    }
    return sorted(unit.relative_to(_REPO_ROOT).as_posix() for unit in units - covered)


def _rule_text() -> str:
    return (_REPO_ROOT / RULE_FILE).read_text(encoding="utf-8")


def _source_of(relative: str) -> str:
    return (_REPO_ROOT / relative).read_text(encoding="utf-8")


def _id(capability: Capability) -> str:
    return f"{capability.source}:{capability.need}"


# --------------------------------------------------------------------------- #
# The guards                                                                  #
# --------------------------------------------------------------------------- #


def test_the_scan_has_a_subject() -> None:
    assert len(_units()) >= _MIN_UNITS, sorted(_units())
    assert len(_capabilities()) >= _MIN_CAPABILITIES


def test_every_marker_is_well_formed() -> None:
    problems = collect(_REPO_ROOT).problems
    assert problems == (), "malformed `Capability:` blocks:\n" + "\n".join(problems)


def test_every_support_unit_is_in_the_catalog() -> None:
    missing = _uncatalogued_units()
    assert missing == [], (
        "a support unit has no `Capability:` block, so a session opening UI or "
        "application code is never told it exists. Add the block to the docstring of "
        "the module that provides it (shape: scripts/render_capability_index.py), then "
        "`python3 scripts/render_capability_index.py --write`:\n"
        + "\n".join(f"  - {unit}" for unit in missing)
    )


def test_every_used_symbol_is_defined_where_the_marker_sits() -> None:
    missing = [
        f"  {_id(c)}: {symbol}"
        for c in _capabilities()
        for symbol in c.symbols
        if symbol not in defined_names(_source_of(c.source))
    ]
    assert missing == [], (
        "a `Use:` symbol is not defined or re-exported by the module carrying the "
        "marker (renamed? moved?):\n" + "\n".join(missing)
    )


def test_every_user_really_imports_the_capability() -> None:
    problems: list[str] = []
    for c in _capabilities():
        user = _REPO_ROOT / c.user
        if not user.is_file():
            problems.append(f"  {_id(c)}: User {c.user} does not exist")
            continue
        if c.user.startswith(c.where):
            problems.append(
                f"  {_id(c)}: User {c.user} is inside the capability itself"
            )
        if not set(c.symbols) & imported_names(user.read_text(encoding="utf-8")):
            problems.append(
                f"  {_id(c)}: User {c.user} imports none of {', '.join(c.symbols)}"
            )
    assert problems == [], "`User:` must be a real consumer:\n" + "\n".join(problems)


def test_a_replacement_is_another_rows_symbol() -> None:
    capabilities = _capabilities()
    known = {symbol for c in capabilities for symbol in c.symbols}
    dangling = [
        f"  {_id(c)} -> {c.replacement}"
        for c in capabilities
        if c.replacement and c.replacement not in known
    ]
    assert dangling == [], (
        "a deprecated row names no catalogued replacement:\n" + "\n".join(dangling)
    )


def test_every_path_the_catalog_names_exists() -> None:
    paths = sorted(set(_CATALOGUED_PATH.findall(_rule_text())))
    missing = [path for path in paths if not (_REPO_ROOT / path).exists()]
    assert paths, "the rule file names no src/ path — the pattern or the file changed"
    assert missing == [], f"{RULE_FILE} names paths that do not exist:\n" + "\n".join(
        f"  - {path}" for path in missing
    )


def test_the_generated_block_is_the_generators_output() -> None:
    block = table_block(_rule_text())
    assert block is not None, f"{RULE_FILE} lost its capabilities markers"
    assert block == render_table(_capabilities()), (
        f"{RULE_FILE}'s generated block differs from the docstrings. Never edit it by "
        "hand: run `python3 scripts/render_capability_index.py --write`."
    )


def test_the_catalog_stays_small() -> None:
    lines = len(_rule_text().splitlines())
    assert lines <= _RULE_MAX_LINES, (
        f"{RULE_FILE} is {lines} lines (ceiling {_RULE_MAX_LINES}); it loads on every UI "
        "or application file. Shorten a row's synonyms, or split by path."
    )


# --------------------------------------------------------------------------- #
# Probes: the guard can fail                                                  #
# --------------------------------------------------------------------------- #

_GOOD = """Summary line.

Capability: Choose a pair
    Also: picker, chooser
    Use: Overlay, Source
    User: src/modules/x/ui/y.py
    Status: stable
"""


def test_a_well_formed_block_parses() -> None:
    parsed = parse_docstring("src/support/a.py", _GOOD)
    assert parsed.problems == ()
    (capability,) = parsed.capabilities
    assert capability.symbols == ("Overlay", "Source")
    assert capability.synonyms == ("picker", "chooser")
    assert capability.where == "src/support/a.py"


def test_a_package_marker_is_located_at_its_directory() -> None:
    parsed = parse_docstring("src/support/k/p/__init__.py", _GOOD)
    assert parsed.capabilities[0].where == "src/support/k/p/"


def test_a_continuation_line_extends_the_field_above() -> None:
    text = _GOOD.replace("Use: Overlay, Source", "Use: Overlay,\n        Source")
    assert parse_docstring("a.py", text).capabilities[0].symbols == (
        "Overlay",
        "Source",
    )


def test_two_blocks_in_one_docstring_are_two_rows() -> None:
    parsed = parse_docstring("a.py", _GOOD + "\n" + _GOOD.replace("pair", "range"))
    assert len(parsed.capabilities) == 2


def test_a_missing_required_field_is_a_problem() -> None:
    text = _GOOD.replace("    User: src/modules/x/ui/y.py\n", "")
    parsed = parse_docstring("a.py", text)
    assert parsed.capabilities == ()
    assert any("missing field `User:`" in p for p in parsed.problems)


def test_a_misspelled_head_is_a_problem_not_a_skipped_row() -> None:
    for head in ("Capabilty: x", "capability: x", "Capabilities: x"):
        parsed = parse_docstring("a.py", head)
        assert parsed.capabilities == ()
        assert parsed.problems, head


def test_an_unknown_field_is_a_problem() -> None:
    text = _GOOD.replace("    Also:", "    Alias:")
    assert any("Alias" in p for p in parse_docstring("a.py", text).problems)


def test_the_status_grammar_is_enforced() -> None:
    assert parse_docstring("a.py", _GOOD.replace("stable", "fine")).problems
    deprecated = parse_docstring("a.py", _GOOD.replace("stable", "deprecated -> Other"))
    assert deprecated.problems == ()
    assert deprecated.capabilities[0].replacement == "Other"


def test_a_user_must_be_a_source_path() -> None:
    text = _GOOD.replace("src/modules/x/ui/y.py", "somewhere")
    assert parse_docstring("a.py", text).problems


def test_a_mention_in_a_string_is_not_an_import() -> None:
    assert imported_names('x = "SymbolPickerOverlay"\n') == set()
    assert imported_names("from pkg.mod import Name as Other\n") == {"Name"}
    assert imported_names("import a.b.c\n") == {"c"}


def test_defined_names_see_classes_functions_imports_and_aliases() -> None:
    source = "from p import R\nclass C: ...\ndef f(): ...\nV = 1\ntype T = int\n"
    assert defined_names(source) == {"R", "C", "f", "V", "T"}
    assert defined_names("def f():\n    class Inner: ...\n") == {"f"}


def test_a_file_belongs_to_its_nearest_unit() -> None:
    root = Path("/r/src/support")
    units = {root / "ui_kit", root / "ui_kit" / "state"}
    nested = root / "ui_kit" / "state" / "adapters" / "s.py"
    assert owning_unit(nested, units) == root / "ui_kit" / "state"
    assert owning_unit(root / "ui_kit" / "x.py", units) == root / "ui_kit"
    assert owning_unit(root / "other" / "x.py", units) is None


def test_with_table_replaces_only_the_block() -> None:
    text = "head\n<!-- capabilities:begin -->\nold\n<!-- capabilities:end -->\ntail\n"
    assert with_table(text, "NEW") == (
        "head\n<!-- capabilities:begin -->\nNEW\n<!-- capabilities:end -->\ntail\n"
    )
