"""Where a screen actually lives, since `EPIC-025` Phase 4 moved every one of
them out of `src/presentation/ui/screens/` and into the module (or `shell/`)
that owns it.

Two guards ask "where do screens live": `test_event_flow_guards.py`'s Guard 3
(no event subscribed by two screens directly) and `test_composition_root.py`'s
Mode 12 (no screen package that nothing routes to). Both went dormant the same
way `ui_trees.py`'s five guards did three times before it existed — the tree
they scanned was deleted and `.rglob()`/`.iterdir()` on a missing path returns
nothing rather than raising, so the check passed on an empty subject instead of
failing (`BOT-141`). This file is the one place that answers "where", the way
`ui_trees.py` is for the UI-styling guards; it decides nothing either — that
stays each guard's own.

**One convention, not a directory shape.** `EPIC-025E`/`F` replaced
`AbstractScreenModule` with a uniform `<name>_screen.py` building a
`ScreenContribution(..., route=<ROUTE_CONSTANT>, ...)`. A screen's directory
depth varies with how many screens its module owns — `backtesting/ui/
backtest_screen.py` sits at the module's `ui/` root (the module's only
screen), `trading/ui/trading/trading_screen.py` and `trading/ui/dashboard/
dashboard_screen.py` each own a subdirectory (the module has two) — so
"screen package" is derived from the file, not guessed from a directory name
matching its route (`database_screen.py`'s own route is `"data_management"`,
which no name-matching scheme would find).

**Roots, found rather than declared.** `src/modules/*/ui` is a glob, not a
fixed tuple: a hand-maintained list is exactly the shape that went stale four
times before `ui_trees.py` existed (its own docstring) — a new module adds its
`ui/` on the pull request that gives it a screen, not on a later one that
remembers to update a registry here too. `src/shell` is the fifth root, the
one screen-owning tree that is not a module. `src/support/ui_kit` is
deliberately not a root: it hosts `base_feed.py`/`health_feed.py`, the shared
Feed layer (the modern address of the old `presentation/ui/common/`), never a
screen of its own — see `screen_owner()`.

Retire when: a screen stops being one file building a literal
`ScreenContribution(route=...)`, or a screen-owning tree appears that this
file's roots do not already cover.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"

#: `ScreenContribution(...)`'s constructor name, as it appears at every call
#: site (`from ...screen_contribution import ScreenContribution`).
_SCREEN_CONTRIBUTION_CALL = "ScreenContribution"


def screen_roots() -> tuple[Path, ...]:
    """Every tree a screen can live under today: each module's `ui/` (found on
    disk, not named one by one) plus `shell/`."""
    return (*sorted(_SRC.glob("modules/*/ui")), _SRC / "shell")


@dataclass(frozen=True)
class ScreenFile:
    """One `*_screen.py` file: its path, the package (directory) it owns —
    Guard 3's per-screen boundary — and the route it declares, when `ast` can
    follow the value statically."""

    path: Path
    package: Path
    route: str | None


def _resolve_route(tree: ast.Module, call: ast.Call) -> str | None:
    """`ScreenContribution(route=...)`'s value: a string literal directly, or
    the module-level `NAME = "..."` constant every screen file assigns and
    passes by name (`BACKTEST_ROUTE`, `DATABASE_ROUTE`, ...)."""
    route_kwarg = next((kw for kw in call.keywords if kw.arg == "route"), None)
    if route_kwarg is None:
        return None
    value = route_kwarg.value
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    if isinstance(value, ast.Name):
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == value.id
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                return node.value.value
    return None


def _screen_route(path: Path) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == _SCREEN_CONTRIBUTION_CALL
        ):
            return _resolve_route(tree, node)
    return None


def screen_files() -> tuple[ScreenFile, ...]:
    """Every `*_screen.py` under the current screen-owning roots."""
    found: list[ScreenFile] = []
    for root in screen_roots():
        for path in sorted(root.rglob("*_screen.py")):
            if "__pycache__" in path.parts:
                continue
            found.append(
                ScreenFile(path=path, package=path.parent, route=_screen_route(path))
            )
    return tuple(found)


def screen_owner(path: Path) -> Path | None:
    """The screen package `path` belongs to: the nearest ancestor directory,
    up to and including a screen-owning root, that itself hosts a
    `*_screen.py` file.

    `None` for a file that sits above every screen inside its root — a Feed
    shared by more than one screen in the same module
    (`modules/trading/ui/equity_feed.py`, read by both `trading/` and
    `dashboard/`) or one shared by the whole application
    (`shell/system_failure_log.py`). That address is this repository's
    `presentation/ui/common/` today: the one place a subscription is allowed
    to live, so Guard 3 must not attribute it to any single screen.
    """
    packages = {sf.package for sf in screen_files()}
    roots = screen_roots()
    candidate = path.parent
    while True:
        if candidate in packages:
            return candidate
        if candidate in roots:
            return None
        if candidate.parent == candidate:
            return None
        candidate = candidate.parent
