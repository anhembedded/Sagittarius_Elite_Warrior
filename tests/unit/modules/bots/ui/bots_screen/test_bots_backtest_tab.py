"""`EPIC-029D` — the Backtest panel of the Bots mode over the bots module's
real graph: the page of a kind with a backtest, an instruction without a
selection, fed the parameters on screen and the planner's terms, and run
through the query the module binds."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    NO_BACKTEST_TEXT,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.kind_backtests import (
    backtest_context,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot import (
    SelectedBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_view import (
    GridBacktestView,
)

from .bots_screen_fixtures import GOOD_CONFIG, BotsScreen, stored

S = BotLifecycleState
_TERMS = ExchangeTerms(
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.00001"),
    min_notional=Decimal(5),
    maker_fee=Decimal("0.001"),
    taker_fee=Decimal("0.001"),
    max_notional_per_order=Decimal(5000),
    max_open_orders=100,
)


def _backtest_page(screen: BotsScreen) -> GridBacktestView | None:
    pages = screen.view.backtest.findChildren(GridBacktestView)
    return pages[0] if pages else None


def test_a_grid_bot_fills_the_backtest_panel_and_no_selection_leaves_a_note(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    assert _backtest_page(screen) is None
    notes = [label.text() for label in screen.view.backtest.findChildren(QLabel)]
    assert notes == [NO_BACKTEST_TEXT]

    screen.view.model.select_requested.emit("a00001")
    screen.settle()

    page = _backtest_page(screen)
    assert page is not None
    # The planner's read brought the terms, so Run is live.
    assert page.run_button.isEnabled()


def test_run_goes_through_the_query_the_module_binds(open_bots_screen, qtbot) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    screen.view.model.select_requested.emit("a00001")
    screen.settle()
    page = _backtest_page(screen)
    assert page is not None

    qtbot.mouseClick(page.run_button, Qt.MouseButton.LeftButton)
    screen.settle()

    # Nothing is stored at 15m: the real handler refuses and offers a sync.
    assert "No 15m candles of BTCUSDT" in page.status.text()
    assert page.sync_button.isVisibleTo(page)


def test_the_context_is_the_parameters_on_screen_and_the_planners_terms(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    selected = SelectedBot(
        BotKindCatalog(()), lambda: datetime(2026, 10, 4, tzinfo=UTC)
    )
    assert backtest_context(selected) is None

    snapshot = screen.view.model.bots[0]
    selected.select(snapshot)
    first = backtest_context(selected)
    assert first is not None
    assert dict(first.config) == GOOD_CONFIG
    assert first.terms is None

    selected.edit({**GOOD_CONFIG, "capital_quote": "1500"})
    selected.take_market(PlannerMarket(_TERMS, None, None, None))
    edited = backtest_context(selected)
    assert edited is not None
    assert edited.config["capital_quote"] == "1500"
    assert edited.terms == _TERMS
    assert (edited.bot_id, edited.symbol) == ("a00001", "BTCUSDT")
