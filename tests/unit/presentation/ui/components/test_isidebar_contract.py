"""`EPIC-016` — `ISidebar` must stay satisfied by the real `Sidebar`.

@details `presentation/` is excluded from the `mypy` gate wholesale, so a
`Protocol` living here has no static enforcement — the same reason
`test_backtest_view_contract.py` exists for `IBacktestView`. This test is the
lighter form: `Sidebar` has no consumer yet that reaches its members through
`ISidebar` specifically (`MainWindow` still imports the concrete class as of
this test — `EPIC-016C` is what switches it), so there is no Presenter-side
source to AST-walk yet. Once `MainWindow` depends on `ISidebar` instead, add
the member-usage walk this file intentionally does not attempt.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.components.sidebar import (
    ISidebar,
    Sidebar,
)


def _declared_members(protocol: type) -> frozenset[str]:
    return frozenset(name for name in dir(protocol) if not name.startswith("_"))


def test_the_contract_is_exactly_five_members() -> None:
    """A count, so a member could not be added and removed in the same diff
    without this test moving — see `IBacktestView`'s own version of this
    test for the full reasoning."""
    assert len(_declared_members(ISidebar)) == 5


@pytest.mark.usefixtures("qapp")
def test_sidebar_satisfies_the_port() -> None:
    """The real `Sidebar` is accepted by `ISidebar` at runtime, not just on
    paper — `runtime_checkable` only checks member *presence*, so this is
    still a weaker guarantee than static typing would give if `presentation/`
    were inside the `mypy` gate, but it is what this layer has."""
    sidebar = Sidebar(sections=(), bottom_actions=())
    assert isinstance(sidebar, ISidebar)
