"""Guard: a class that subscribes to the event bus must be named in the app.

## The blind spot, stated once (`BUG-126`, [`CS-002`](../../../Docs/CASE_STUDIES/CS-002_the_subscriber_nobody_built.md))

`EPIC-008` §1 found that `UiActionFailedEvent` and `TaskFailed` had **zero
subscribers** — a UI slot that raised or a background task that died left no
trace anywhere a user could see — and ranked it P1. `EPIC-008G` answered with
`SystemErrorFeed`: a class that subscribed to both, normalised them, and
re-emitted them on a Qt signal. It was written, it was unit-tested, its task
was closed.

Nothing ever constructed it. Not a screen, not the composition root, not a
script. Its subscriptions live in `__init__`, so a class nobody builds
subscribes to nothing, and the P1 finding stayed true for two more epics behind
a green gate.

Every check in this repository was satisfied:

  · the feed's own test file constructed it and passed — a unit test supplies
    the construction production was missing, which is precisely the step
    under test;
  · `test_event_flow_guards.py` checked that subscriptions address events by
    **class** rather than by string — true of a subscription that never runs;
  · `ruff`'s dead-code rules (`ERA`, `F401`) see an unused *import* or a
    commented-out line, never a class that is exported and simply never called;
  · `mypy` type-checks a class no caller reaches exactly as happily as one
    every caller reaches.

So this guard reads the one fact all of them missed: a subscribing class whose
name appears in **no other code** in `src/` or `scripts/` cannot be constructed
by the application, therefore its subscriptions never happen, therefore the
events it claims to handle reach nobody.

## Why the check is "named", not "called"

`ClassName(...)` is the obvious test and it is too strict here: a screen class
is handed to a registry as a bare reference and constructed by the registry
later (`shell/legacy_screens.py`, `presentation/ui/screens/*/module.py`), which
is a construction this file cannot see. Being *named* somewhere else is the
weakest claim that still excludes the defect, and measured against this tree it
separates cleanly — eight subscribers reachable, one orphan, no false positives.

It reads identifiers from the **AST**, never the file text. A first draft
grepped for the name and called `SystemErrorFeed` reachable, because two
docstrings mentioned it. A guard that a comment can satisfy is not a guard.

Stdlib only, like the other architecture guards here.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("no pyproject.toml above this file")


_REPO_ROOT = _repo_root()

#: Where a subscriber may be *defined*: the application's own source.
_DEFINITION_ROOT = "src"

#: Where a construction may live. `scripts/` counts — a probe or an end-to-end
#: script is a real consumer, and demanding `src/` would push a script-only
#: subscriber into an allowlist for no gain.
_REFERENCE_ROOTS = ("src", "scripts")

#: The subscribe verb, on the bus itself or on a `QtEventBridge` wrapping it
#: (`self._events.on(...)` inside a `BaseFeed`).
_SUBSCRIBE = "on"


def _trees(*roots: str) -> dict[Path, ast.Module]:
    found: dict[Path, ast.Module] = {}
    for root in roots:
        for path in sorted((_REPO_ROOT / root).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                found[path] = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:  # pragma: no cover - a parse error is ruff's job
                continue
    return found


def _subscribes(node: ast.ClassDef) -> bool:
    return any(
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == _SUBSCRIBE
        and call.args
        for call in ast.walk(node)
    )


def _subscribing_classes(
    trees: Mapping[Path, ast.Module], definition_root: Path
) -> dict[str, tuple[Path, ast.ClassDef]]:
    found: dict[str, tuple[Path, ast.ClassDef]] = {}
    for path, tree in trees.items():
        if not path.is_relative_to(definition_root):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and _subscribes(node):
                found[node.name] = (path, node)
    return found


def _identifiers(tree: ast.AST, excluding: ast.AST | None = None) -> set[str]:
    """Every name this module mentions **in code** — a docstring cannot
    contribute one, which is the whole reason this reads the AST."""
    excluded = set(map(id, ast.walk(excluding))) if excluding is not None else set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in excluded:
            continue
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _orphans(
    trees: Mapping[Path, ast.Module], definition_root: Path
) -> list[tuple[str, Path]]:
    """Subscribing classes no other module in `trees` names."""
    orphaned: list[tuple[str, Path]] = []
    for name, (home, classdef) in sorted(
        _subscribing_classes(trees, definition_root).items()
    ):
        reachable = any(
            name in _identifiers(tree, excluding=classdef if path == home else None)
            for path, tree in trees.items()
        )
        if not reachable:
            orphaned.append((name, home))
    return orphaned


def test_every_bus_subscriber_is_reachable() -> None:
    """The check `BUG-126` needed. One second, against the whole tree."""
    trees = _trees(*_REFERENCE_ROOTS)
    orphans = _orphans(trees, _REPO_ROOT / _DEFINITION_ROOT)

    assert orphans == [], (
        "these classes subscribe to the event bus and nothing in src/ or "
        "scripts/ names them, so the application never constructs one — their "
        "events reach nobody, exactly as in BUG-126:\n"
        + "\n".join(
            f"  {name} ({home.relative_to(_REPO_ROOT).as_posix()})"
            for name, home in orphans
        )
        + "\n\nEither wire it where it belongs, or delete it. A subscriber that "
        "only a test constructs is dead code wearing the shape of a fix."
    )


def test_the_guard_has_a_subject() -> None:
    """A path-scanning guard that has lost its subject passes, faster — the
    failure `ui_trees.py` was written after paying for three times. Locked at
    "more than five" rather than an exact number, because the count moves with
    every feed the epic adds or retires."""
    subscribers = _subscribing_classes(
        _trees(_DEFINITION_ROOT), _REPO_ROOT / _DEFINITION_ROOT
    )

    assert len(subscribers) > 5, (
        f"only {len(subscribers)} subscribing class(es) found in "
        f"{_DEFINITION_ROOT}/. Either the application stopped subscribing "
        f"through `.{_SUBSCRIBE}(...)` — in which case this guard reads nothing "
        "and the verb it looks for has changed — or the scan root moved."
    )


def test_the_guard_can_actually_fail() -> None:
    """Fed a subscriber nobody names, the guard must say so; fed the same
    subscriber with one reference, it must go quiet.

    A guard never seen red is a guard nobody knows runs — and this one exists
    *because* four separate checks were green over the defect. Asserting both
    directions is what distinguishes it from them."""
    root = Path("/synthetic/src")
    orphan_module = ast.parse(
        "class Listener:\n"
        "    def __init__(self, bus):\n"
        "        bus.on(SomeEvent, self._handle)\n"
    )
    mentions_it_only_in_prose = ast.parse('"""Listener does the work."""\n')

    unwired = _orphans(
        {
            root / "listener.py": orphan_module,
            root / "boot.py": mentions_it_only_in_prose,
        },
        root,
    )
    wired = _orphans(
        {
            root / "listener.py": orphan_module,
            root / "boot.py": ast.parse("listener = Listener(bus)\n"),
        },
        root,
    )

    assert [name for name, _ in unwired] == ["Listener"], (
        "the guard accepted a subscriber that only a docstring mentions — it is "
        f"reading file text rather than the AST. Got {unwired}."
    )
    assert wired == [], f"the guard rejected a subscriber that is constructed: {wired}"
