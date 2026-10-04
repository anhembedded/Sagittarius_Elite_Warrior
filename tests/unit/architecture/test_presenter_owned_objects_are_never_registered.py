"""A Presenter-owned object is never registered in the DI container
(`async-ui-action-rule.md`, "Presenter-owned, constructor-injected, never
self-resolving, never DI-registered or discoverable").

**Why this guard exists** (`EPIC-030F`). The rule's tag was a shell pipeline,
`grep -rn "Coordinator\\|Presenter" src | grep "singleton(\\|bind("`, wired to
nothing — no test, no gate ran it — and it matched by *name*, so the
app-wide `UiStateCoordinator` (`support/ui_kit/state/ui_state_coordinator.py`,
registered on purpose by `presentation/ui/app_bootstrapper.py`) was a false
positive the day it landed. A check that is never run and is wrong when it
is run is no check.

**What is forbidden, by definition site, not by name.** Every class *defined*
in a `*_presenter.py`, in a `**/coordinators/*_coordinator.py`, in a
`modules/*/ui/**/*_coordinator.py`, or in the backtest chart host file
(`PythonBacktestChartHost`, `BacktestChartHostFactory` — view-owned and
transient by their own docstring). `UiStateCoordinator` lives in none of
those places, so it is not flagged.

**What a registration is.** A call `<x>.singleton(...)`, `<x>.bind(...)` or
`<x>.scoped(...)` with exactly two positional arguments, the first a plain
type name (`IFoo` / `module.IFoo`) — the `IContainer` shape. A
`BindingGroup.bind(widget, owner, attribute, coerce)` has four arguments and
a widget expression first, so it is not one. The registration's arguments
are walked whole, into lambdas and nested calls, and a bare function name
defined in the same file (`container.singleton(IStore, _build_store)`) is
followed into that function's body.

Not followed: a factory imported from another file. Measured 2026-10-04 no
registration needs it; a registration that hides a presenter-owned class
behind an imported builder is a review question (`pr-review` G4).

Retire when: presenters and coordinators can no longer reach a container at
all (constructor injection only, `PresenterManager` passes no container), so
nothing could register one.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"
_MODULES_ROOT = _SRC_ROOT / "modules"
_CHART_HOST_FILE = (
    _SRC_ROOT / "modules" / "backtesting" / "ui" / "logic" / "backtest_chart_host.py"
)

_REGISTRATION_METHODS = frozenset({"singleton", "bind", "scoped"})
_REGISTRATION_ARITY = 2

#: Measured 2026-10-04 (see `test_the_scan_has_a_subject`): 12 presenter
#: files, 23 coordinator files, 123 registration calls. Floors well below,
#: so they catch a lost subject, not churn.
_MIN_PRESENTER_CLASSES = 5
_MIN_COORDINATOR_CLASSES = 10
_MIN_REGISTRATIONS = 50


# --------------------------------------------------------------------------- #
# Pure helpers                                                                #
# --------------------------------------------------------------------------- #


def defined_class_names(source: str) -> set[str]:
    """Every class defined anywhere in `source` (nested ones included)."""
    return {
        node.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ClassDef)
    }


def _is_type_reference(node: ast.expr) -> bool:
    return isinstance(node, ast.Name | ast.Attribute)


def registration_calls(tree: ast.AST) -> list[ast.Call]:
    """Every `IContainer`-shaped registration call in `tree`."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _REGISTRATION_METHODS
        and len(node.args) == _REGISTRATION_ARITY
        and not node.keywords
        and _is_type_reference(node.args[0])
    ]


def _names_in(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return names


def registered_forbidden_names(
    source: str, forbidden: set[str]
) -> list[tuple[int, str]]:
    """`(line, class name)` for each forbidden class a registration in
    `source` names — directly, inside a lambda or nested call, or inside the
    body of a same-file function the registration passes by name."""
    tree = ast.parse(source)
    local_functions = {
        node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    found: set[tuple[int, str]] = set()
    for call in registration_calls(tree):
        names: set[str] = set()
        for arg in call.args:
            names |= _names_in(arg)
            if isinstance(arg, ast.Name) and arg.id in local_functions:
                names |= _names_in(local_functions[arg.id])
        found.update((call.lineno, name) for name in names & forbidden)
    return sorted(found)


# --------------------------------------------------------------------------- #
# The tree                                                                    #
# --------------------------------------------------------------------------- #


def _presenter_files() -> list[Path]:
    return sorted(_SRC_ROOT.rglob("*_presenter.py"))


def _coordinator_files() -> list[Path]:
    return sorted(
        {
            *_SRC_ROOT.rglob("coordinators/*_coordinator.py"),
            *_MODULES_ROOT.glob("*/ui/**/*_coordinator.py"),
        }
    )


def _classes_in(files: list[Path]) -> set[str]:
    return {
        name for path in files for name in defined_class_names(path.read_text("utf-8"))
    }


def _forbidden_classes() -> set[str]:
    return (
        _classes_in(_presenter_files())
        | _classes_in(_coordinator_files())
        | _classes_in([_CHART_HOST_FILE])
    )


def _source_files() -> list[Path]:
    return sorted(p for p in _SRC_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def test_the_scan_has_a_subject() -> None:
    """A guard with nothing forbidden, or no registration to look at, passes
    everything (HLD §9.3 rule 4)."""
    presenters = _classes_in(_presenter_files())
    coordinators = _classes_in(_coordinator_files())
    assert len(presenters) >= _MIN_PRESENTER_CLASSES, presenters
    assert len(coordinators) >= _MIN_COORDINATOR_CLASSES, coordinators
    assert {"PythonBacktestChartHost", "BacktestChartHostFactory"} <= _classes_in(
        [_CHART_HOST_FILE]
    )
    registrations = sum(
        len(registration_calls(ast.parse(path.read_text("utf-8"))))
        for path in _source_files()
    )
    assert registrations >= _MIN_REGISTRATIONS, registrations


def test_the_app_wide_ui_state_coordinator_is_not_presenter_owned() -> None:
    """The false positive the old grep had: registered on purpose, and defined
    outside every presenter-owned location."""
    assert "UiStateCoordinator" not in _forbidden_classes()


def test_no_presenter_owned_object_is_registered() -> None:
    forbidden = _forbidden_classes()
    offenders = [
        f"  {path.relative_to(_REPO_ROOT).as_posix()}:{line}  {name}"
        for path in _source_files()
        for line, name in registered_forbidden_names(path.read_text("utf-8"), forbidden)
    ]
    assert offenders == [], (
        "a Presenter-owned object is registered in the container. Presenters,\n"
        "their coordinators and the view-owned chart host are constructed by\n"
        "their owner and passed in through the constructor — never registered,\n"
        "never resolved (`async-ui-action-rule.md`):\n" + "\n".join(offenders)
    )


# --------------------------------------------------------------------------- #
# Probes: the guard can fail                                                  #
# --------------------------------------------------------------------------- #

_FORBIDDEN = {"SyncCoordinator", "BacktestChartHost", "DashboardPresenter"}


def test_a_coordinator_registered_as_a_singleton_is_flagged() -> None:
    source = "container.singleton(SyncCoordinator, SyncCoordinator(x))\n"
    assert registered_forbidden_names(source, _FORBIDDEN) == [(1, "SyncCoordinator")]


def test_a_factory_lambda_building_a_forbidden_class_is_flagged() -> None:
    source = "container.bind(IFoo, lambda c: BacktestChartHost())\n"
    assert registered_forbidden_names(source, _FORBIDDEN) == [(1, "BacktestChartHost")]


def test_a_dotted_reference_is_flagged() -> None:
    source = "c.scoped(IFoo, presenters.DashboardPresenter)\n"
    assert registered_forbidden_names(source, _FORBIDDEN) == [(1, "DashboardPresenter")]


def test_a_same_file_builder_function_is_followed() -> None:
    source = (
        "def _build(c):\n"
        "    return SyncCoordinator(c.resolve(IX))\n"
        "container.singleton(IFoo, _build)\n"
    )
    assert registered_forbidden_names(source, _FORBIDDEN) == [(3, "SyncCoordinator")]


def test_the_app_wide_ui_state_coordinator_registration_is_not_flagged() -> None:
    """`app_bootstrapper.py`'s real line, against the real forbidden set."""
    source = "app_engine.context.container.singleton(UiStateCoordinator, state_coordinator)\n"
    assert registered_forbidden_names(source, _forbidden_classes()) == []


def test_a_binding_group_bind_is_not_a_registration() -> None:
    """`BindingGroup.bind(widget, owner, attribute, coerce)` shares the method
    name only; even naming a forbidden class inside it is not a registration."""
    source = (
        "bindings.bind(self._widgets[key], owner_of(vm, f), 'attr', SyncCoordinator)\n"
    )
    assert registration_calls(ast.parse(source)) == []
    assert registered_forbidden_names(source, _FORBIDDEN) == []


def test_defined_class_names_sees_nested_classes() -> None:
    source = "class Outer:\n    class _Inner:\n        pass\n"
    assert defined_class_names(source) == {"Outer", "_Inner"}
