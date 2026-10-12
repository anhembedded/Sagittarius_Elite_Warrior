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
   module, or, for a marker in a package's `__init__.py`, of a module directly in that
   package (a module past the 400-line ceiling keeps its marker in the package docstring
   instead of growing, `test_god_files_only_shrink.py`); each `User` file exists, lies outside the capability's own directory and
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

import re
from pathlib import Path

from Sagittarius_Elite_Warrior.scripts.render_capability_index import (
    RULE_FILE,
    Capability,
    collect,
    render_table,
    table_block,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.capability_catalog_checks import (
    defined_names,
    dotted_module,
    imports_the_capability,
    owning_unit,
    symbol_sites,
    unit_directories,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SUPPORT = "src/support"

#: Ceiling for the rule file, in lines. The catalog loads on every UI or application file, so
#: it stays small; it may fall, never rise without the owner's decision.
_RULE_MAX_LINES = 120
#: Floors that catch a lost scan (the markers or the units vanishing), not churn.
_MIN_CAPABILITIES = 25
_MIN_UNITS = 10

_CATALOGUED_PATH = re.compile(r"`(src/[^`\s]+)`")


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


def _names_defined_for(capability: Capability) -> set[str]:
    return {
        name
        for site in symbol_sites(_REPO_ROOT, capability)
        for name in defined_names(site.read_text(encoding="utf-8"))
    }


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
        if symbol not in _names_defined_for(c)
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
        if not imports_the_capability(user.read_text(encoding="utf-8"), c):
            problems.append(
                f"  {_id(c)}: User {c.user} imports none of {', '.join(c.symbols)} "
                f"from {dotted_module(c.source)} (or a package above it)"
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
