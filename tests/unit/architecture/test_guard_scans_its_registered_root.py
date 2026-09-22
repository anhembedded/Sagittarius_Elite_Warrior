"""`test_scanned_roots_are_not_empty.py` proves a registered root **exists**;
it never proves the guard it describes actually **reads** that root (`BOT-142`).

`BUG-131` is why this exists: `test_indicator_script_conventions.py`'s own
`_SCRIPTS_DIR`/`_DOMAIN_DIR` constants pointed at a directory `EPIC-025`
deleted three days earlier, while `scanned_roots_registry.py`'s row for that
exact guard held the *correct* path the whole time. The registry's own
non-emptiness check passed throughout — a registered row can be right while
the guard it names checks something else, or nothing, and nothing before this
file noticed.

**Mechanism.** For each guard registered in `GUARDS`, parse its source with
`ast`, find every `.glob(pattern)`/`.rglob(pattern)` call whose receiver
resolves — through simple `/`-joined literal chains, aliasing, and
tuple-of-chains iterated in a `for`/comprehension — to a path relative to the
repository root, and compare that resolved set against the guard's registered
rows by **directory containment**, not exact equality: a registered root is
confirmed if the guard actually scans it or somewhere under it; a resolved
scan is explained if it falls under some registered root. Containment, not
equality, because a guard legitimately scanning a subdirectory of its
declared root for one purpose (`test_trading_view_contract.py`'s only
`.glob()` call targets `.../trading/coordinators`, a child of its registered
`.../trading`) is not the defect this file exists to catch — a scan landing
somewhere with **no relationship at all** to any registered row is
(`BUG-131`'s exact shape: `src/domain/...` registered as
`src/support/indicators/...`). The glob **pattern** is deliberately not
compared: measured across the real registry, several guards register a
simplified pattern (`*.py`) for a root whose real call uses a more specific
one (`application/**/*.py`, `*/SKILL.md`) — same root, different but
overlapping literal spelling, not a relocation.

**What this cannot resolve, measured against all 41 registered guards (this
file's own row included), named here rather than silently skipped
(`testing-rule.md`'s `Retire when:` convention) — 19 guards fall into one of
these:**

- **Imported root table** — roots come from a tuple imported from another
  module (`ui_trees.py`'s `UI_TREES`/`UI_TREE_ROWS`/`existing_ui_trees()`),
  not literal in the guard's own AST: `test_card_layer_structure.py`,
  `test_widget_guards_hold.py`, `test_palette_is_the_only_color_source.py`,
  `test_quick_widget_only_in_embed.py`, `test_preview_fixtures_exist.py`.
- **Root behind a function parameter** — the call's receiver is a plain
  parameter (`def _iter_python_files(root): ... root.rglob(...)`); the real
  value only exists at each call site, which this file-local check does not
  cross: `test_screen_layer_structure.py` (same helper as
  `test_card_layer_structure.py`, doubly out of scope there).
- **Bare-string tuple joined at the call site** — `(_REPO_ROOT /
  root).rglob(pattern)` where `root` iterates a tuple of plain strings
  (`("src", "scripts")`), not pre-built `/`-chains:
  `test_every_resolved_type_is_bound.py`,
  `test_a_bus_subscriber_is_constructed.py`,
  `test_no_root_is_found_by_counting.py`, `test_python_floor.py`.
- **The pattern, not the root, is the variable** —
  `_SRC_ROOT.glob(glob)` where `glob` iterates a tuple of pattern strings
  (`_QT_FREE_GLOBS`) — the exact shape this task's own brief named:
  `test_module_domain_is_qt_free.py`; `test_fake_helpers_are_verified.py`'s
  pattern is a named constant rather than an inline literal, same effect.
- **Runtime-discovered subdirectory** — the root includes a segment only
  knowable by walking the filesystem first (`for module_id in
  _MODULES_ROOT.iterdir(): (_MODULES_ROOT / module_id).rglob(...)`):
  `test_module_declarations.py`, `test_no_cross_screen_imports.py`,
  `test_composition_root.py` (several of its modes).
- **No `glob`/`rglob`/`iterdir` call at all** — the guard proves its subject
  by reading one named file directly (`.read_text()`/`.is_file()`) or via a
  helper imported from another module, never calling one of the three
  methods this check understands on a path it builds itself:
  `test_module_boundaries.py` (`scanned_files()` from `git_tracked_paths.py`),
  `test_self_check_process.py`, `test_binance_endpoint_config_keys_are_dead.py`,
  and this file itself (it reads each registered guard's source via
  `.read_text()`, never scanning a directory the way it checks other guards
  for).

None of these are guessed — `python3` with this file's own resolver was run
against the real tree before writing this docstring; the list above is that
run's output. A guard moving out of this list (gaining a resolvable literal
scan) needs no edit here — it is picked up automatically. A guard that should
resolve but does not is a gap in this check's resolver, not a defect in that
guard; `test_every_guard_is_either_resolved_or_documented` is what forces a
new gap to be named rather than silently absorbed into "unresolvable".

Retire when: a fully general path-expression evaluator replaces this (not
planned — the six shapes above cover every real case in this repository
today, and forcing 100% coverage in one pass was explicitly out of scope for
`BOT-142`).
"""

from __future__ import annotations

import ast
from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.architecture.scanned_roots_registry import (
    GUARDS,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]

_GLOB_METHODS = frozenset({"glob", "rglob"})

#: Guards this check's resolver cannot statically follow, one line each —
#: see the module docstring for the six named shapes and why. A stale entry
#: (a guard that no longer exists, or has changed shape) is caught by
#: `test_every_unresolvable_guard_is_a_real_registered_guard` below.
_UNRESOLVABLE_GUARDS: dict[str, str] = {
    "tests/unit/architecture/test_module_boundaries.py": "scans via `scanned_files()`, imported from `git_tracked_paths.py` — no glob/rglob/iterdir call of its own.",
    "tests/unit/architecture/test_every_resolved_type_is_bound.py": "root joined from a bare-string tuple (`_ROOTS`) at the call site, not a literal chain.",
    "tests/unit/architecture/test_module_domain_is_qt_free.py": "the glob *pattern* (`_QT_FREE_GLOBS`), not the root, is the loop variable.",
    "tests/unit/architecture/test_module_declarations.py": "scans `_MODULES_ROOT / module_id`, a directory name discovered by `.iterdir()` at runtime.",
    "tests/unit/architecture/test_fake_helpers_are_verified.py": "pattern is a named constant (`_FAKE_GLOB`), not an inline literal; second scan root is runtime-discovered.",
    "tests/unit/architecture/test_a_bus_subscriber_is_constructed.py": "root joined from a bare-string tuple (`_REFERENCE_ROOTS`) at the call site, not a literal chain.",
    "tests/unit/architecture/test_no_root_is_found_by_counting.py": "root joined from a bare-string tuple (`_SCAN_ROOTS`) at the call site, not a literal chain.",
    "tests/unit/architecture/test_screen_layer_structure.py": "`.rglob()`'s receiver is `_iter_python_files(root)`'s plain parameter, not a literal chain visible at the call site.",
    "tests/unit/architecture/test_card_layer_structure.py": "same `_iter_python_files(root)` helper as above, called with an imported `UI_TREES`/`existing_ui_trees()` root table — doubly out of scope.",
    "tests/unit/presentation/ui/test_widget_guards_hold.py": "roots come from `UI_TREE_ROWS`, imported from `ui_trees.py`, not literal in this file's own AST.",
    "tests/unit/architecture/test_no_cross_screen_imports.py": "scans `package_dir.rglob(...)` where `package_dir` is a subdirectory name discovered by `.iterdir()` at runtime.",
    "tests/unit/presentation/ui/test_preview_fixtures_exist.py": "one scan root is runtime-discovered via `.iterdir()`; the other iterates a root table imported from `ui_trees.py`.",
    "tests/unit/presentation/ui/test_palette_is_the_only_color_source.py": "roots come from `UI_TREE_ROWS`, imported from `ui_trees.py`, not literal in this file's own AST.",
    "tests/unit/architecture/test_quick_widget_only_in_embed.py": "roots include `*UI_TREE_ROWS`, imported from `ui_trees.py`, spread into a tuple this file does not itself define.",
    "tests/unit/config/test_binance_endpoint_config_keys_are_dead.py": "reads named files directly (`.read_text()`) — no glob/rglob/iterdir call.",
    "tests/sanity/test_composition_root.py": "several of its modes discover a root via `.iterdir()` at runtime (module/screen package names); not a literal chain.",
    "tests/sanity/test_self_check_process.py": "proves `src/main.py` exists via a direct path check — no glob/rglob/iterdir call.",
    "tests/sanity/test_python_floor.py": "root joined from a bare-string tuple (`_FIRST_PARTY_DIRS`) at the call site, not a literal chain.",
    "tests/unit/architecture/test_guard_scans_its_registered_root.py": "reads each registered guard file's own source via `.read_text()` — no glob/rglob/iterdir call of its own; the exact same shape as `test_scanned_roots_are_not_empty.py`, registered next to it for the same reason.",
}

#: (guard, root, pattern) rows registered for a real reason this check's
#: resolver cannot see. Named individually, like `EMPTY_BY_DESIGN`, because an
#: exemption has to name the exact row it excuses.
_ROW_EXCEPTIONS: frozenset[tuple[str, str, str]] = frozenset(
    {
        # Proven by a single named file's `.read_text()`, not a directory glob.
        (
            "tests/unit/config/test_credentials_never_reach_a_git_tracked_file.py",
            "src/config",
            "*.json",
        ),
        # `BOT-141`'s Guard 3 scans via `screen_roots()`, imported from
        # `screen_files.py` — an "imported root table" shape, the same one
        # `UI_TREE_ROWS` already puts out of scope for other guards, just
        # returned by a function call here rather than a tuple. This file's
        # only *resolvable* literal call is Guard 1's own `_SRC.rglob(...)`,
        # registered separately as `("src", "*.py")` and confirmed for real.
        (
            "tests/unit/test_event_flow_guards.py",
            "src/modules/backtesting/ui",
            "*.py",
        ),
        (
            "tests/unit/test_event_flow_guards.py",
            "src/modules/market_data/ui",
            "*.py",
        ),
        ("tests/unit/test_event_flow_guards.py", "src/modules/strategy/ui", "*.py"),
        ("tests/unit/test_event_flow_guards.py", "src/modules/trading/ui", "*.py"),
        ("tests/unit/test_event_flow_guards.py", "src/shell", "*.py"),
    }
)


def _is_parents_hop(node: ast.expr) -> bool:
    """`Path(__file__).resolve().parents[N]` — a repo-root landmark hop."""
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "parents"
        and isinstance(node.value.value, ast.Call)
        and isinstance(node.value.value.func, ast.Attribute)
        and node.value.value.func.attr == "resolve"
    )


def _is_landmark_root_function(func_def: ast.FunctionDef) -> bool:
    """A zero-argument function that walks `Path(__file__).resolve().parents`
    looking for a landmark file — the shape every guard's own local
    `_repo_root()`/`_bot_root()` helper uses instead of a hop count
    (`test_no_root_is_found_by_counting.py`'s own rule is why)."""
    if func_def.args.args or func_def.args.vararg or func_def.args.kwarg:
        return False
    dumped = ast.dump(func_def)
    return "__file__" in dumped and "parents" in dumped


def _root_variable_names(tree: ast.Module) -> set[str]:
    """Every name (any scope) bound to 'the repository root': a direct
    `parents[N]` hop, or a call to a same-file landmark-search function."""
    functions = {
        node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    roots: set[str] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            continue
        name = node.targets[0].id
        value = node.value
        is_landmark_call = (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id in functions
            and _is_landmark_root_function(functions[value.func.id])
        )
        if _is_parents_hop(value) or is_landmark_call:
            roots.add(name)
    return roots


def _literal_chain(
    node: ast.expr, roots: set[str], paths: dict[str, str]
) -> str | None:
    """The repo-root-relative path a `/`-chain, alias or root reference
    builds, or `None` if it involves anything else (a loop variable, a
    function parameter, an imported name)."""
    if _is_parents_hop(node):
        return ""
    if isinstance(node, ast.Name):
        if node.id in roots:
            return ""
        return paths.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _literal_chain(node.left, roots, paths)
        if left is None:
            return None
        if not isinstance(node.right, ast.Constant) or not isinstance(
            node.right.value, str
        ):
            return None
        segment = node.right.value
        return f"{left}/{segment}" if left else segment
    return None


def _literal_list(
    node: ast.expr,
    roots: set[str],
    paths: dict[str, str],
    tuple_paths: dict[str, list[str]],
) -> list[str] | None:
    """A `Tuple`/`List` of chains (or a name already resolved to one),
    resolved element-by-element, or `None` if any element is not a literal
    chain (a bare string, a loop variable, ...)."""
    if isinstance(node, ast.Name):
        return tuple_paths.get(node.id)
    if isinstance(node, (ast.Tuple, ast.List)):
        resolved: list[str] = []
        for element in node.elts:
            if isinstance(element, ast.Starred):
                inner = _literal_list(element.value, roots, paths, tuple_paths)
                if inner is None:
                    return None
                resolved.extend(inner)
                continue
            chain = _literal_chain(element, roots, paths)
            if chain is None:
                return None
            resolved.append(chain)
        return resolved
    return None


def _bindings(
    tree: ast.Module, roots: set[str]
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Every name (any scope) bound to a resolvable chain or tuple-of-chains,
    in source order — later assignments may reference earlier ones
    (`_DOMAIN_DIR = _SCRIPTS_DIR`)."""
    paths: dict[str, str] = {}
    tuple_paths: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            continue
        name = node.targets[0].id
        chain = _literal_chain(node.value, roots, paths)
        if chain is not None:
            paths[name] = chain
            continue
        resolved_list = _literal_list(node.value, roots, paths, tuple_paths)
        if resolved_list is not None:
            tuple_paths[name] = resolved_list
    return paths, tuple_paths


def _loop_target_paths(
    tree: ast.Module,
    roots: set[str],
    paths: dict[str, str],
    tuple_paths: dict[str, list[str]],
) -> dict[str, set[str]]:
    """`for target in ITER` and comprehension `for target in ITER`, wherever
    `ITER` resolves to a tuple of chains: `target` stands for each of them
    inside that loop's body."""
    targets: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.comprehension)):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        resolved_list = _literal_list(node.iter, roots, paths, tuple_paths)
        if resolved_list is not None:
            targets.setdefault(node.target.id, set()).update(resolved_list)
    return targets


def _resolved_rows(guard_path: Path) -> set[tuple[str, str]]:
    """Every (root, pattern) this guard's own AST literally scans via
    `.glob(pattern)`/`.rglob(pattern)`, following simple chains, aliases and
    tuple-of-chains loops. Empty when nothing resolves (see
    `_UNRESOLVABLE_GUARDS`)."""
    tree = ast.parse(guard_path.read_text(encoding="utf-8"))
    roots = _root_variable_names(tree)
    paths, tuple_paths = _bindings(tree, roots)
    loop_targets = _loop_target_paths(tree, roots, paths, tuple_paths)

    found: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _GLOB_METHODS
        ):
            continue
        if len(node.args) != 1 or not isinstance(node.args[0], ast.Constant):
            continue
        pattern = node.args[0].value
        if not isinstance(pattern, str):
            continue
        receiver = node.func.value
        direct = _literal_chain(receiver, roots, paths)
        if direct is not None:
            found.add((direct, pattern))
            continue
        if isinstance(receiver, ast.Name) and receiver.id in loop_targets:
            for candidate_root in loop_targets[receiver.id]:
                found.add((candidate_root, pattern))
    return found


def _contains(root: str, candidate: str) -> bool:
    """`candidate` is `root` itself, or a path under it."""
    return candidate == root or candidate.startswith(f"{root}/")


def test_every_unresolvable_guard_is_a_real_registered_guard() -> None:
    """A stale `_UNRESOLVABLE_GUARDS` entry (the guard was deleted, renamed
    or retargeted) would otherwise sit unnoticed forever, exempting nothing —
    the same trap `EMPTY_BY_DESIGN`'s own completeness check guards against."""
    registered = {guard for guard, _ in GUARDS}
    stale = sorted(set(_UNRESOLVABLE_GUARDS) - registered)
    assert stale == [], (
        f"_UNRESOLVABLE_GUARDS names guard(s) no longer in GUARDS: {stale}"
    )


def test_every_row_exception_is_a_real_registered_row() -> None:
    registered_rows = {
        (guard, root, pattern) for guard, rows in GUARDS for root, pattern in rows
    }
    stale = sorted(_ROW_EXCEPTIONS - registered_rows)
    assert stale == [], f"_ROW_EXCEPTIONS names row(s) not in GUARDS: {stale}"


def test_every_guard_is_either_resolved_or_documented() -> None:
    """No guard may silently fall through as 'nothing resolved' — it is
    either checked for real (below) or named in `_UNRESOLVABLE_GUARDS` with a
    reason (`testing-rule.md`'s scope-honesty convention)."""
    undocumented = sorted(
        guard
        for guard, _ in GUARDS
        if not _resolved_rows(_REPO_ROOT / guard) and guard not in _UNRESOLVABLE_GUARDS
    )
    assert undocumented == [], (
        "these guards resolve no literal glob/rglob call and are not named in "
        f"_UNRESOLVABLE_GUARDS (add an entry with the real reason): {undocumented}"
    )


def test_every_resolvable_guard_scans_its_registered_root() -> None:
    """The heart of `BOT-142`: for every guard whose AST resolves at least
    one literal scan, every registered row must be confirmed by something the
    guard actually scans, and every actual scan must fall under some
    registered row — by directory containment (module docstring explains
    why, not exact equality)."""
    failures: list[str] = []
    for guard, rows in GUARDS:
        if guard in _UNRESOLVABLE_GUARDS:
            continue
        resolved = _resolved_rows(_REPO_ROOT / guard)
        if not resolved:
            continue  # reported by test_every_guard_is_either_resolved_or_documented
        registered_roots = {root for root, _ in rows}
        resolved_roots = {root for root, _ in resolved}

        unexplained = sorted(
            path
            for path in resolved_roots
            if not any(_contains(root, path) for root in registered_roots)
        )
        unconfirmed = sorted(
            root
            for root in registered_roots
            if not any(_contains(root, path) for path in resolved_roots)
            and not any(
                exc_guard == guard and exc_root == root
                for exc_guard, exc_root, _ in _ROW_EXCEPTIONS
            )
        )
        if unexplained:
            failures.append(
                f"{guard}: scans {unexplained} — not under any row registered "
                f"for it ({sorted(registered_roots)})"
            )
        if unconfirmed:
            failures.append(
                f"{guard}: registered root(s) {unconfirmed} — nothing this "
                "guard's own AST scans falls under them"
            )

    assert failures == [], (
        "guard(s) whose registered root and real scan disagree:\n  "
        + "\n  ".join(failures)
    )


def test_the_check_can_actually_fail() -> None:
    """`BUG-131`'s exact shape, reproduced synthetically (no real file
    touched): a registry row naming the *correct*, current path while the
    guard's own source still resolves to the tree `EPIC-025` deleted three
    days earlier. `_resolved_rows` must report the stale path, and it must
    not be confirmed by the correct registered root."""
    stale_source = (
        "from pathlib import Path\n"
        "_BOT_ROOT = Path(__file__).resolve().parents[3]\n"
        "_SCRIPTS_DIR = _BOT_ROOT / 'src' / 'domain' / 'indicator_scripts'\n"
        "list(_SCRIPTS_DIR.glob('*.py'))\n"
    )
    tree = ast.parse(stale_source)
    roots = _root_variable_names(tree)
    paths, _tuple_paths = _bindings(tree, roots)
    found: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _GLOB_METHODS
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            direct = _literal_chain(node.func.value, roots, paths)
            if direct is not None:
                found.add((direct, node.args[0].value))

    assert found == {("src/domain/indicator_scripts", "*.py")}
    registered_root = "src/support/indicators/indicator_scripts"
    assert not any(_contains(registered_root, path) for path, _ in found), (
        "the stale-shape probe must NOT be confirmed by the correct registered "
        "root — if it is, the check cannot catch BUG-131's real shape"
    )

    correct_source = stale_source.replace(
        "'src' / 'domain' / 'indicator_scripts'",
        "'src' / 'support' / 'indicators' / 'indicator_scripts'",
    )
    tree = ast.parse(correct_source)
    roots = _root_variable_names(tree)
    paths, _tuple_paths = _bindings(tree, roots)
    found = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _GLOB_METHODS
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            direct = _literal_chain(node.func.value, roots, paths)
            if direct is not None:
                found.add((direct, node.args[0].value))
    assert any(_contains(registered_root, path) for path, _ in found), (
        "the corrected probe must be confirmed by the registered root"
    )
