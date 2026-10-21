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

`ClassName(...)` is the obvious test and it is too strict here: a screen's
view/presenter factories are handed to a registry as bare references and
constructed by the router later (every `*_screen()` in `modules/*/ui/` and
`shell/{welcome,settings}/`), which is a construction this file cannot see.
Being *named* somewhere else is the
weakest claim that still excludes the defect, and measured against this tree it
separates cleanly — eight subscribers reachable, one orphan, no false positives.

It reads identifiers from the **AST**, never the file text. A first draft
grepped for the name and called `SystemErrorFeed` reachable, because two
docstrings mentioned it. A guard that a comment can satisfy is not a guard.

Stdlib only, like the other architecture guards here.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest


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


def _named_by_path(call: ast.Call) -> set[str]:
    """The class a `Deferred("package.module:Class")` or a `ModuleEntry(id, "Class")` names.

    Both construct a class they do not import (`PRO-014`), so the path or the name in the call
    is the reference that makes the application build it. Only these two calls count: a
    docstring or a log line that happens to spell a class name still does not."""
    callee = call.func
    callee_name = callee.id if isinstance(callee, ast.Name) else None
    strings = [
        arg.value
        for arg in call.args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    ]
    if callee_name == "Deferred":
        return {text.rpartition(":")[2] for text in strings if ":" in text}
    if callee_name == "ModuleEntry":
        return set(strings)
    return set()


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
        elif isinstance(node, ast.Call):
            names |= _named_by_path(node)
    return names


def _orphans(
    trees: Mapping[Path, ast.Module], definition_root: Path
) -> list[tuple[str, Path]]:
    """Subscribing classes no other module in `trees` names.

    Each module is read once for the names it mentions (`BUG-244`): asking per subscriber walked
    every module again, subscribers times modules walks of the whole tree (22,892 walks, about
    45 s under a profiler, 11 s quiet), which a loaded CI runner stretched past the 60 s limit.
    Only the module that defines a subscriber is read again, without that class's own body."""
    mentioned = {path: _identifiers(tree) for path, tree in trees.items()}
    orphaned: list[tuple[str, Path]] = []
    for name, (home, classdef) in sorted(
        _subscribing_classes(trees, definition_root).items()
    ):
        elsewhere = any(
            name in names for path, names in mentioned.items() if path != home
        )
        reachable = elsewhere or name in _identifiers(trees[home], excluding=classdef)
        if not reachable:
            orphaned.append((name, home))
    return orphaned


def test_every_bus_subscriber_is_reachable() -> None:
    """The check `BUG-126` needed, against the whole tree (about three seconds: each module is
    read once, `BUG-244`)."""
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


def test_each_module_is_read_once_however_many_subscribers_there_are(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`BUG-244`: the cost of the scan grows with the modules plus the subscribers, never their
    product. Three subscribers nobody names, five modules: asking per subscriber read the modules
    fifteen times, and the real tree (2,159 modules, fifteen subscribers) took 11 s quiet and more
    than 60 s on a loaded runner. Counted, not timed, so a slow machine cannot hide it."""
    root = Path("/synthetic/src")
    trees: dict[Path, ast.Module] = {
        root / f"listener_{index}.py": ast.parse(
            f"class Listener{index}:\n"
            "    def __init__(self, bus):\n"
            "        bus.on(SomeEvent, self._handle)\n"
        )
        for index in range(3)
    }
    for index in range(2):
        trees[root / f"module_{index}.py"] = ast.parse("value = 1\n")
    reads: list[ast.AST] = []
    real = _identifiers

    def counting(tree: ast.AST, excluding: ast.AST | None = None) -> set[str]:
        reads.append(tree)
        return real(tree, excluding)

    monkeypatch.setattr(sys.modules[__name__], "_identifiers", counting)

    orphans = _orphans(trees, root)

    assert [name for name, _ in orphans] == ["Listener0", "Listener1", "Listener2"]
    assert len(reads) <= len(trees) + 3, (
        f"{len(reads)} module reads for {len(trees)} modules and 3 subscribers: "
        "the scan reads every module again for each subscriber"
    )


def test_a_subscriber_named_outside_its_own_body_in_its_own_module_is_constructed() -> (
    None
):
    """The defining module is read again without the class's own body (`BUG-244` kept that rule
    when each module began to be read once): the class naming itself does not count, a line of
    its module that builds it does."""
    root = Path("/synthetic/src")
    body_only = ast.parse(
        "class Listener:\n"
        "    def __init__(self, bus):\n"
        "        bus.on(SomeEvent, self._handle)\n"
        "    def again(self):\n"
        "        return Listener(None)\n"
    )
    built_in_its_module = ast.parse(
        "class Listener:\n"
        "    def __init__(self, bus):\n"
        "        bus.on(SomeEvent, self._handle)\n"
        "listener = Listener(bus)\n"
    )

    assert [n for n, _ in _orphans({root / "a.py": body_only}, root)] == ["Listener"]
    assert _orphans({root / "a.py": built_in_its_module}, root) == []
