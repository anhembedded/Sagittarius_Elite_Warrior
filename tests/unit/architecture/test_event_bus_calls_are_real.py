"""`BUG-124` — every method this app calls on the event bus must exist on it.

## Why a guard and not just a fix

The Start button on the Welcome screen raised
`self.event_bus.publish(StartRequested())` for two pull requests. `publish` is
the verb of the app's **own** port, `IEventPublisher`; `emit` is the verb of
the **engine's** `IEventBus`, which is what a `BasePresenter` actually holds.
Two vocabularies for one idea, and the wrong one on the wrong object.

Three layers each failed to notice, which is the reason this file exists rather
than a one-line fix:

1. **The type checker could not see it.** `IContainer.resolve` is declared
   `(abstract: type[Any]) -> Any`, so `BasePresenter.event_bus` is `Any`, and
   every attribute access on `Any` typechecks. `src/shell/` *is* inside the
   mypy gate and the gate was green.
2. **The suite could not see it.** The Welcome test handed the Presenter a
   hand-written double defining `publish`, `on` **and** `subscribe` — the
   union of two different interfaces plus a method that exists on neither. A
   double shaped like that cannot disagree with the code under test.
3. **Nothing imports the shell wholesale.** `tests/sanity/test_composition_root
   .py::_import_all_under` imports every module under `application/use_cases`
   and `domain/strategies`; an `AttributeError` inside a Qt slot in `shell/`
   is reached only by running the app.

So the honest check is the smallest one that does not depend on any of the
three: read the source, find every call made on something named like the bus,
and compare the method names against the interface itself.

## What this does and does not claim

It is a **name** check, not a type check — it cannot tell that the argument is
the right shape. That is fine: the class of bug it exists for is a caller
reaching for a verb from the wrong vocabulary, and a wrong verb is exactly
what a name check catches. The allowed set is read off `IEventBus` at runtime
rather than pinned as a literal, so an engine release that renames `emit`
fails here with the new name in the message instead of drifting quietly.

Subject size, measured when it was written: 20 `on`, 6 `emit`, and the one
`publish` that was the bug. A guard with 26 real call sites is not a guard
watching an empty room.
"""

from __future__ import annotations

import ast
from pathlib import Path

from sagittarius_engine.interfaces.i_event_bus import IEventBus

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: Where application code lives. `tests/` is deliberately absent: a test may
#: legitimately build its own recorder around the bus, and the double this
#: guard's own bug hid behind is now the real `MemoryEventBus` anyway.
_SCAN_ROOTS = (_REPO_ROOT / "src", _REPO_ROOT / "scripts")

#: An attribute whose name says "this is the event bus". Matching by name is
#: what keeps the guard independent of the `Any` that defeated mypy: it needs
#: no inferred type to know what the object is meant to be.
_BUS_NAMES = frozenset({"event_bus", "_event_bus", "bus", "_bus"})

#: Read off the interface, not typed out here — see the module docstring.
_REAL_METHODS = frozenset(
    name for name in dir(IEventBus) if not name.startswith("_")
) | {
    # `QtEventBridge` is the engine's own wrapper around the bus and a
    # presenter holds one under the same naming convention; its two methods
    # are a legitimate thing to call on something named `_bus`.
    "subscribe_on_main_thread",
    "dispose",
}


def _python_files() -> list[Path]:
    return [
        path
        for root in _SCAN_ROOTS
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def _bus_calls(tree: ast.AST) -> list[tuple[str, str, int]]:
    """Every `<something bus-shaped>.<method>(...)` in one module, as
    `(receiver, method, line)`."""
    found: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        receiver = func.value
        name = (
            receiver.attr
            if isinstance(receiver, ast.Attribute)
            else receiver.id
            if isinstance(receiver, ast.Name)
            else None
        )
        if name in _BUS_NAMES:
            found.append((name, func.attr, node.lineno))
    return found


def _all_bus_calls() -> list[tuple[Path, str, str, int]]:
    calls: list[tuple[Path, str, str, int]] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for receiver, method, line in _bus_calls(tree):
            calls.append((path, receiver, method, line))
    return calls


def test_no_call_invents_a_method_the_event_bus_does_not_have() -> None:
    """The check `BUG-124` needed. A verb borrowed from another port — the
    app's `IEventPublisher.publish` on the engine's `IEventBus` — is an
    `AttributeError` the moment a user presses the button, and nothing else in
    the repository is positioned to say so before then."""
    offenders = [
        f"{path.relative_to(_REPO_ROOT).as_posix()}:{line}: {receiver}.{method}()"
        for path, receiver, method, line in _all_bus_calls()
        if method not in _REAL_METHODS
    ]

    assert offenders == [], (
        "a method was called on the event bus that the bus does not have. "
        f"`IEventBus` offers {sorted(_REAL_METHODS)}.\n"
        "`publish()` is the app's own `IEventPublisher` — a different port "
        "with a different contract; the engine bus's verb is `emit()`.\n"
        + "\n".join(offenders)
    )


def test_the_guard_has_a_subject() -> None:
    """Locked at "more than ten" rather than an exact count: the number moves
    with every screen that subscribes, and a ratchet on it would be noise. It
    reaching zero would mean the naming convention changed and this guard
    stopped reading anything, which is the only outcome worth failing on."""
    calls = _all_bus_calls()

    assert len(calls) > 10, (
        f"only {len(calls)} bus call(s) found in {[str(r) for r in _SCAN_ROOTS]}. "
        "Either the app stopped using the event bus, or the attribute naming "
        f"convention moved away from {sorted(_BUS_NAMES)} and this guard is "
        "now inspecting nothing."
    )
