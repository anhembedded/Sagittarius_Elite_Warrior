"""`EPIC-033C` — the `IShownAsMode` port stays declared, both ways.

The window (`presentation/`) and one of the two presenters that implement
the port are excluded from mypy, and the window dispatches with
`isinstance(presenter, IShownAsMode)`. A presenter whose method drifted from
the port would be skipped without a sound and its screen would never go live,
so this module reads the sources: the port declares exactly what the window
calls, and every class in `src/` that defines `on_mode_shown` takes the
port's one argument. Since `EPIC-033D` the window also dispatches on
`CommandPresenter`, so "what the window calls" is checked against both.

Retire when: `presentation/` and the implementers are under the mypy gate,
which would catch both directions statically.
"""

from __future__ import annotations

import ast
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_shown_as_mode import (
    IHiddenAsMode,
    IShownAsMode,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_presenter import (
    CommandPresenter,
)

_SRC = Path(__file__).resolve().parents[4] / "src"
_WINDOW = _SRC / "presentation" / "ui" / "main_window.py"
_METHOD = "on_mode_shown"


#: Every port the window dispatches a presenter on with `isinstance`.
_PRESENTER_PORTS: tuple[type, ...] = (IShownAsMode, IHiddenAsMode, CommandPresenter)


def _declared(port: type) -> frozenset[str]:
    return frozenset(
        name
        for name, value in vars(port).items()
        if callable(value) and not name.startswith("_")
    )


def _implementers() -> dict[str, ast.FunctionDef]:
    """class qualified by its file -> its `on_mode_shown` definition."""
    found: dict[str, ast.FunctionDef] = {}
    for path in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name == IShownAsMode.__name__:
                continue
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == _METHOD:
                    found[f"{path.relative_to(_SRC).as_posix()}::{node.name}"] = item
    return found


def _called_on_presenters() -> frozenset[str]:
    tree = ast.parse(_WINDOW.read_text(encoding="utf-8"))
    return frozenset(
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "presenter"
        and node.func.attr != "dispose"
    )


def test_the_ports_declare_exactly_what_the_window_calls() -> None:
    assert _declared(IShownAsMode) == {_METHOD}
    assert _declared(IHiddenAsMode) == {"on_mode_hidden"}
    assert _called_on_presenters() == frozenset().union(
        *(_declared(port) for port in _PRESENTER_PORTS)
    )


def test_every_implementer_takes_the_ports_one_source_argument() -> None:
    implementers = _implementers()
    assert implementers, "the scan of src/ found no implementer at all"
    for where, method in implementers.items():
        arguments = [argument.arg for argument in method.args.args]
        annotation = method.args.args[-1].annotation
        assert arguments == ["self", "source"], where
        assert isinstance(annotation, ast.Name), where
        assert annotation.id == "NavigationSource", where


def test_the_implementers_are_the_known_two() -> None:
    """A new implementer is a deliberate change: add it here, with its reason
    for going live on a show rather than on construction."""
    assert set(_implementers()) == {
        "modules/market_data/ui/data_management_presenter.py::DataManagementPresenter",
        "modules/trading/ui/market/market_presenter.py::MarketPresenter",
    }
