"""`EPIC-013B` — the Presenter↔View contract must stay declared, both ways.

@details `presentation/` is excluded from the `mypy` gate wholesale
(`pyproject.toml`, `EPIC-002A`), so a `Protocol` living in this layer has
**no** static enforcement at all. Without something mechanical, `IBacktestView`
would drift exactly the way the engine's `IView` did — it declares one method,
`bind()`, that no View in either repo implements and nothing ever noticed.

So this module walks the Presenter-side sources with `ast` and fails when the
members they reach for and the members `IBacktestView` declares stop matching.
Both directions matter: an undeclared member means the contract is again
implicit, and a declared-but-unused member means the port asks implementers for
something no consumer needs (`architecture-rule.md` §1 "I").
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_chart_host import (
    BacktestChartHostFactory,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.chart_controls import (
    BacktestChartControls,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.ports import (
    IBacktestChartControls,
    IBacktestChartHostFactory,
    IBacktestView,
)

_SCREEN_DIR = (
    Path(__file__).resolve().parents[6]
    / "src"
    / "presentation"
    / "ui"
    / "screens"
    / "backtest"
)

#: The modules that sit on the Presenter side of the boundary. `preview.py` is
#: deliberately absent: it is a standalone developer harness that constructs a
#: `BackTestView()` itself and calls `resize()` on it, which is a QWidget
#: operation and not part of what a Presenter asks of a View. Including it
#: would drag `resize()` into the port and make every future View owe a method
#: no Presenter calls.
_PRESENTER_SIDE = (
    _SCREEN_DIR / "backtest_presenter.py",
    _SCREEN_DIR / "signal_wiring.py",
    _SCREEN_DIR / "state_persistence.py",
    *sorted((_SCREEN_DIR / "coordinators").glob("*.py")),
)

#: Names that hold a View on the Presenter side. `presenter.view` is reached
#: through the first of these as `<something>.view.<member>`, which the visitor
#: below handles as a nested attribute access.
_VIEW_NAMES = frozenset({"view", "_view"})


def _declared_members(protocol: type) -> frozenset[str]:
    """Every method and annotated attribute a `Protocol` declares itself."""
    return frozenset(
        name for name in dir(protocol) if not name.startswith("_")
    ) | frozenset(getattr(protocol, "__annotations__", {}))


#: Builtins that reach a member by *string* instead of by attribute syntax.
#: `EPIC-013C` found `getattr(presenter.view, "chart_mode", <default>)` in
#: `coordinators/factory.py` — a real member of the contract that plain
#: attribute-access walking could not see, hidden behind a default that would
#: have masked any View failing to provide it. `architecture-rule.md` §2.1
#: names this form explicitly as forbidden capability probing.
_STRING_PROBES = frozenset({"getattr", "hasattr", "setattr"})


class _ViewAttributeCollector(ast.NodeVisitor):
    """Collects every View member reached, by syntax or by string."""

    def __init__(self) -> None:
        self.members: set[str] = set()
        self.probes: set[str] = set()

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if self._is_view_expression(node.value):
            self.members.add(node.attr)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        probed = self._probed_member(node)
        if probed is not None:
            self.members.add(probed)
            self.probes.add(probed)
        self.generic_visit(node)

    @classmethod
    def _probed_member(cls, node: ast.Call) -> str | None:
        """`getattr(<view>, "name", ...)` -> `"name"`, else `None`."""
        if not isinstance(node.func, ast.Name) or node.func.id not in _STRING_PROBES:
            return None
        if len(node.args) < 2 or not cls._is_view_expression(node.args[0]):
            return None
        name = node.args[1]
        if isinstance(name, ast.Constant) and isinstance(name.value, str):
            return name.value
        return None

    @staticmethod
    def _is_view_expression(node: ast.expr) -> bool:
        """True for `view`, `self.view`, `self._view`, `presenter.view`, ..."""
        if isinstance(node, ast.Name):
            return node.id in _VIEW_NAMES
        if isinstance(node, ast.Attribute):
            return node.attr in _VIEW_NAMES
        return False


def _collect() -> tuple[frozenset[str], dict[str, str]]:
    """Members reached, plus which file string-probed each one."""
    members: set[str] = set()
    probes: dict[str, str] = {}
    for path in _PRESENTER_SIDE:
        collector = _ViewAttributeCollector()
        collector.visit(ast.parse(path.read_text(encoding="utf-8")))
        members |= collector.members
        probes.update(dict.fromkeys(collector.probes, path.name))
    return frozenset(members), probes


def _members_used_by_presenter_side() -> frozenset[str]:
    return _collect()[0]


def test_every_member_the_presenter_side_uses_is_declared() -> None:
    """No member may be reached without `IBacktestView` naming it."""
    undeclared = _members_used_by_presenter_side() - _declared_members(IBacktestView)
    assert not undeclared, (
        "Presenter-side code reaches these View members without "
        f"IBacktestView declaring them: {sorted(undeclared)}. "
        "architecture-rule.md §2.1 forbids the implicit contract — add them "
        "to the port (or stop using them)."
    )


def test_every_declared_member_is_actually_used() -> None:
    """No member may be declared that nothing on the Presenter side calls."""
    unused = _declared_members(IBacktestView) - _members_used_by_presenter_side()
    assert not unused, (
        f"IBacktestView declares members nothing uses: {sorted(unused)}. "
        "That is the exact state the engine's IView is in (it declares "
        "bind(), implemented by nobody). Interface Segregation "
        "(architecture-rule.md §1 'I'): a port states what its consumer "
        "needs, not more."
    )


def test_no_view_member_is_reached_by_string() -> None:
    """`getattr(view, "x", default)` is forbidden even when `x` is declared.

    @details A string probe with a default silently accepts a View that does
    not satisfy the contract — the failure the port exists to make loud. It is
    also invisible to attribute-access walking, which is how `chart_mode` sat
    outside `IBacktestView` while every other member was covered.
    """
    _, probes = _collect()
    assert not probes, (
        "View members reached by string instead of attribute access: "
        f"{ {name: where for name, where in sorted(probes.items())} }. "
        "architecture-rule.md §2.1 forbids capability probing — read the "
        "attribute directly and let a missing one fail loudly."
    )


def test_the_contract_is_exactly_fifteen_members() -> None:
    """A count, so a two-sided drift cannot cancel itself out.

    @details Both tests above compare *sets*, so simultaneously deleting one
    member and adding another would leave them green while the port silently
    changed shape. `EPIC-013B` measured 14; `EPIC-013C` added `chart_mode`,
    which had been reached by string. Changing this number is a deliberate act
    that should show up in a diff.
    """
    assert len(_declared_members(IBacktestView)) == 15


@pytest.mark.usefixtures("qapp")
def test_backtest_view_satisfies_the_port() -> None:
    """The real View is accepted by the port at runtime, not just on paper."""
    assert isinstance(BackTestView(), IBacktestView)


@pytest.mark.usefixtures("qapp")
def test_concrete_chart_controls_and_factory_satisfy_their_ports() -> None:
    """The two ports `IBacktestView` speaks in are satisfied too.

    @details Without this, `chart_controls` and `set_chart_host_factory()`
    could keep their annotations while the concrete widget/factory drifted
    out from under them — the annotation would then be decoration, which is
    the failure mode `architecture-rule.md` §2.1 calls out for Protocols
    specifically: nothing fails until a type checker runs, and here none does.
    """
    assert isinstance(BacktestChartHostFactory(), IBacktestChartHostFactory)
    assert isinstance(BacktestChartControls(), IBacktestChartControls)
