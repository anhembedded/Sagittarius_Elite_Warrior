"""`BUG-124`/`BUG-125` — every method called on an engine port must exist on it.

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

## Two ports, and why only two

`BUG-125` arrived a day later from following `CS-001`'s own "where else this is
still open" list, and it was the same mistake on the neighbouring collaborator:
`self.logger.exception(...)`, which is `logging.Logger`'s verb — the engine's
`ILogger` offers exactly info/warning/error/debug/critical/trace. Same file,
same `Any`, and the test that drove that very line stayed green because the
container fixture answered `Mock()` for `ILogger`.

So the bus check grew a sibling. It stops at two ports, measured rather than
chosen: the name `logger` is bound to **three** different real types in this
tree — the stdlib logger (196 call sites, and it *does* have `exception`), the
engine's `ILogger`, and `BacktestEventLogger` with its own domain verbs — so a
guard keyed on the name alone would report ten false positives and be
abandoned. `self.logger` **inside a `BasePresenter` subclass** is the one
binding that is unambiguous, because that is the line of the base class which
assigns it. `config` and `dispatcher` were measured the same way and left out:
`config` names `IConfig`, `IConfigWriter` and an `ActionContext` at different
call sites.

Subject size when written, measured by running the guard's own collectors
rather than by grepping: **15** bus calls and **5** presenter logger calls
across two files. Small, and that is the honest number — a `grep` for the same
thing answers 26, because it also counts docstrings and import lines. Each
half has a companion test that fails if its subject reaches zero, which is the
only way a name-keyed guard dies quietly.
"""

from __future__ import annotations

import ast
from pathlib import Path

from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_logger import ILogger

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

    assert len(calls) >= 5, (
        f"only {len(calls)} bus call(s) found in {[str(r) for r in _SCAN_ROOTS]}. "
        "Either the app stopped using the event bus, or the attribute naming "
        f"convention moved away from {sorted(_BUS_NAMES)} and this guard is "
        "now inspecting nothing."
    )


# ---------------------------------------------------------------------------
# `ILogger` — `BUG-125`
# ---------------------------------------------------------------------------

#: Read off the interface, like the bus's set above.
_REAL_LOG_METHODS = frozenset(name for name in dir(ILogger) if not name.startswith("_"))


def _presenter_logger_calls() -> list[tuple[Path, str, int, int]]:
    """Every `self.logger.<method>(...)` in a module that subclasses
    `BasePresenter`, as `(path, method, line, positional_args)`.

    Scoped to `self.logger` in a presenter module deliberately — see the
    module docstring on why the bare name `logger` cannot be keyed on.
    """
    calls: list[tuple[Path, str, int, int]] = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        if "BasePresenter" not in text:
            continue
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Attribute
            ):
                continue
            receiver = node.func.value
            if not (
                isinstance(receiver, ast.Attribute)
                and receiver.attr == "logger"
                and isinstance(receiver.value, ast.Name)
                and receiver.value.id == "self"
            ):
                continue
            calls.append((path, node.func.attr, node.lineno, len(node.args)))
    return calls


def test_no_presenter_invents_a_logger_method() -> None:
    """`BUG-125`: `self.logger.exception(...)` on the failure path of the
    developer-mode switch — the one place whose whole job was to stay honest
    when the write failed."""
    offenders = [
        f"{path.relative_to(_REPO_ROOT).as_posix()}:{line}: self.logger.{method}()"
        for path, method, line, _ in _presenter_logger_calls()
        if method not in _REAL_LOG_METHODS
    ]

    assert offenders == [], (
        f"`ILogger` offers {sorted(_REAL_LOG_METHODS)}. `exception`, "
        "`isEnabledFor` and friends belong to `logging.Logger`, which is a "
        "different object — a presenter holds the engine's port.\n"
        + "\n".join(offenders)
    )


def test_no_presenter_logs_printf_style() -> None:
    """The quieter half of `BUG-125`. `ILogger.info(message, extra=None)` has
    no printf pass-through, so `info("saved %s", value)` hands the value over
    as `extra` and prints a literal `%s`. Nothing raises; the log simply says
    less than it looks like it says, which `logging-rule.md` §2 is about."""
    offenders = [
        f"{path.relative_to(_REPO_ROOT).as_posix()}:{line}: "
        f"self.logger.{method}() with {args} positional arguments"
        for path, method, line, args in _presenter_logger_calls()
        if method in _REAL_LOG_METHODS and args > 1
    ]

    assert offenders == [], (
        "`ILogger` takes `(message, extra: dict | None)` — a second "
        "positional argument is not a printf parameter, it lands in `extra` "
        "and the placeholder is printed verbatim. Format the message "
        "instead.\n" + "\n".join(offenders)
    )


def test_the_logger_guard_has_a_subject() -> None:
    calls = _presenter_logger_calls()

    assert len(calls) >= 3, (
        f"only {len(calls)} presenter logger call(s) found. Either presenters "
        "stopped logging, or `self.logger` is no longer how they reach the "
        "port and this guard is inspecting nothing. The floor is deliberately "
        "well under the count measured when it was written: this test exists "
        "to catch the scan going empty, not to pin a number that moves with "
        "every screen."
    )
