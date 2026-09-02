"""`EPIC-021I` — the Presenter<->View contract must stay declared, both
ways.

@details Same mechanism as `test_backtest_view_contract.py`
(`EPIC-013B`): `presentation/` is excluded from the `mypy` gate wholesale
(`pyproject.toml`, `EPIC-002A`), so a bare `Protocol` here has no static
enforcement at all. This module walks the Presenter-side sources with
`ast` and fails when the members they reach for and the members
`ITradingView` declares stop matching, in either direction.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.i_trading_view import (
    ITradingView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_view import (
    TradingView,
)

_SCREEN_DIR = (
    Path(__file__).resolve().parents[6]
    / "src"
    / "presentation"
    / "ui"
    / "screens"
    / "trading"
)

#: The modules that sit on the Presenter side of the boundary.
#: `preview.py` and `module.py` are deliberately absent — neither reaches
#: for a View member the way a Presenter/Coordinator does (`preview.py`
#: constructs a bare `TradingView()` for a developer harness; `module.py`
#: only imports the class).
_PRESENTER_SIDE = (
    _SCREEN_DIR / "trading_presenter.py",
    *sorted((_SCREEN_DIR / "coordinators").glob("*.py")),
)

#: Names that hold a View on the Presenter side.
_VIEW_NAMES = frozenset({"view", "_view"})


def _declared_members(protocol: type) -> frozenset[str]:
    """Every method and annotated attribute a `Protocol` declares itself."""
    return frozenset(
        name for name in dir(protocol) if not name.startswith("_")
    ) | frozenset(getattr(protocol, "__annotations__", {}))


#: Builtins that reach a member by *string* instead of by attribute syntax.
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
    """No member may be reached without `ITradingView` naming it."""
    undeclared = _members_used_by_presenter_side() - _declared_members(ITradingView)
    assert not undeclared, (
        "Presenter-side code reaches these View members without "
        f"ITradingView declaring them: {sorted(undeclared)}. "
        "architecture-rule.md §2.1 forbids the implicit contract — add them "
        "to the port (or stop using them)."
    )


def test_every_declared_member_is_actually_used() -> None:
    """No member may be declared that nothing on the Presenter side calls."""
    unused = _declared_members(ITradingView) - _members_used_by_presenter_side()
    assert not unused, (
        f"ITradingView declares members nothing uses: {sorted(unused)}. "
        "Interface Segregation (architecture-rule.md §1 'I'): a port states "
        "what its consumer needs, not more."
    )


def test_no_view_member_is_reached_by_string() -> None:
    """`getattr(view, "x", default)` is forbidden even when `x` is declared."""
    _, probes = _collect()
    assert not probes, (
        "View members reached by string instead of attribute access: "
        f"{ {name: where for name, where in sorted(probes.items())} }. "
        "architecture-rule.md §2.1 forbids capability probing — read the "
        "attribute directly and let a missing one fail loudly."
    )


def test_the_contract_is_exactly_four_members() -> None:
    """A count, so a two-sided drift cannot cancel itself out."""
    assert len(_declared_members(ITradingView)) == 4


@pytest.mark.usefixtures("qapp")
def test_trading_view_satisfies_the_port() -> None:
    """The real View is accepted by the port at runtime, not just on paper."""
    assert isinstance(TradingView(), ITradingView)
