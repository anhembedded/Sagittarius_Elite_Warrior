"""`EPIC-029H` precondition — the Bots tab drives the real Grid executor.

`test_grid_bot_against_fake_server.py` dispatches the use cases itself; this
file presses the tab's own buttons instead. The Bots screen is built on the
composed app's container (its real dispatcher, thread pool, bus and stores),
over the fake Binance server, and Start, Pause, Resume and Stop go from the
screen to the `EPIC-029E` executor and out to the exchange. Only the bot's
queue and pacer and the fake's missing websocket are substituted, as in
`grid_fake_exchange`. The screen's answers arrive on the thread pool, so each
step waits on a named condition (`qtbot.waitUntil`), never a sleep.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from PySide6.QtWidgets import QTableView
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    bots_commands,
    lifecycle_id,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_dialogs import (
    BotsDialogs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_presenter import (
    BotsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_column_checks import (
    alignment_problems,
    digit_font_problems,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    PRECISION_ROLE,
    Precision,
)

from .grid_fake_exchange import (
    GRID,
    SPOT,
    SYMBOL,
    BootedApp,
    FakeExchange,
    booted,
    ladder,
    resting,
)

S = BotLifecycleState
_WAIT_MS = 10_000


class _Screen:
    """The Bots tab on the app's container; Stop always sells the base."""

    def __init__(self, app: BootedApp, qtbot: Any) -> None:
        self.app = app
        self.qtbot = qtbot
        self.stops: list[str] = []
        self.view = BotsView()
        qtbot.addWidget(self.view)
        self.presenter = BotsPresenter(
            self.view,
            app.engine.context.container,
            dialogs=BotsDialogs(
                ask_new_bot=lambda _kinds, _venues: None,
                ask_stop=self._ask_stop,
                confirm_delete=lambda _bot: False,
                ask_arm_strategy=lambda _venue, _form: False,
                allow_real_money=lambda _venue, _what: True,
            ),
        )
        self.actions = bound_actions(
            self.view, bots_commands(BOTS_ROUTE), self.presenter.bind_commands
        )

    def _ask_stop(self, bot: BotSnapshot) -> BaseHandling:
        self.stops.append(bot.bot_id)
        return BaseHandling.SELL_AT_MARKET

    def select(self, bot_id: str) -> None:
        model = self.view.model
        self.qtbot.waitUntil(
            lambda: any(bot.bot_id == bot_id for bot in model.bots), timeout=_WAIT_MS
        )
        model.select_requested.emit(bot_id)

    def press(self, action: BotAction) -> None:
        """Waits for the command to be enabled, as a person would, then
        triggers it (`EPIC-033D`: the Bots menu's action)."""
        command = self.actions.action(lifecycle_id(action))
        self.qtbot.waitUntil(command.isEnabled, timeout=_WAIT_MS)
        command.trigger()

    def wait_for(self, bot_id: str, state: BotLifecycleState) -> None:
        self.qtbot.waitUntil(
            lambda: self.app.bot(bot_id).state is state, timeout=_WAIT_MS
        )


@pytest.fixture
def screen(exchange: FakeExchange, qtbot: Any) -> Iterator[_Screen]:
    with booted(exchange) as app:
        opened = _Screen(app, qtbot)
        yield opened
        opened.presenter.dispose()


def _created(app: BootedApp) -> str:
    created = app.engine.dispatch(
        CreateBotCommand, CreateBotCommand("grid", "grid", SPOT, SYMBOL, GRID)
    )
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None
    return created.bot_id


def test_start_pause_resume_and_stop_from_the_tab_reach_the_exchange(
    screen: _Screen,
) -> None:
    app = screen.app
    bot_id = _created(app)
    screen.select(bot_id)

    screen.press(BotAction.START)
    screen.wait_for(bot_id, S.RUNNING)

    placed = ladder(app.runtime(bot_id))
    assert placed
    assert resting(app.urls) == placed

    screen.press(BotAction.PAUSE)
    screen.wait_for(bot_id, S.PAUSED)

    # Paused keeps the resting orders and places nothing new.
    assert resting(app.urls) == placed

    screen.press(BotAction.RESUME)
    screen.wait_for(bot_id, S.RUNNING)

    assert resting(app.urls) == ladder(app.runtime(bot_id))

    screen.press(BotAction.STOP)
    screen.wait_for(bot_id, S.STOPPED)

    assert screen.stops == [bot_id]
    # The dialog's answer (sell the base) reached the executor, not only the
    # stop itself: on the fake both answers leave nothing resting.
    assert app.runtime(bot_id).sell_base_on_stop
    assert resting(app.urls) == {}


def test_a_running_bots_orders_are_quoted_in_its_venues_filters(
    screen: _Screen,
) -> None:
    """`EPIC-033N`, on the composed app: the Orders panel answers each price
    with the tick size the venue's own metadata cache holds once the bot has
    read its terms, so a price prints in whole ticks."""
    app = screen.app
    bot_id = _created(app)
    screen.select(bot_id)
    screen.press(BotAction.START)
    screen.wait_for(bot_id, S.RUNNING)
    orders = screen.view.orders.orders
    screen.qtbot.waitUntil(lambda: bool(orders.rows), timeout=_WAIT_MS)

    context = app.engine.context.container.resolve(IVenueContexts).get(SPOT)
    filters = context.metadata_cache.get(SYMBOL)
    price = orders.index(0, orders.column("price"))
    quantity = orders.index(0, orders.column("quantity"))

    assert filters is not None
    assert orders.data(price, PRECISION_ROLE) == Precision(filters.tick_size)
    assert orders.data(quantity, PRECISION_ROLE) == Precision(filters.step_size)


def test_the_running_bots_tables_show_each_column_as_its_kind(
    screen: _Screen,
) -> None:
    """`EPIC-033N`, the conformance suite's column checks on the Bots mode
    with rows in its tables (the booted suite sees no bot): the list, the
    resting orders and the venues' strategies align by kind, and their
    prices, quantities and money are in the fixed-pitch font."""
    app = screen.app
    bot_id = _created(app)
    screen.select(bot_id)
    screen.press(BotAction.START)
    screen.wait_for(bot_id, S.RUNNING)
    view = screen.view
    screen.qtbot.waitUntil(lambda: bool(view.orders.orders.rows), timeout=_WAIT_MS)
    view.show()
    screen.qtbot.waitExposed(view)
    view.surface.dock_of(view.orders).raise_()
    measured = [
        table.objectName()
        for table in view.findChildren(QTableView)
        if table.isVisible() and table.model().rowCount()
    ]

    assert {"tblBots", "tblBotOrders"} <= set(measured)
    assert alignment_problems(view, view) == []
    assert digit_font_problems(view, view) == []


def _plan_says(screen: _Screen, text: str) -> bool:
    return screen.view.plan.readiness_header.text() == text


def test_a_new_bot_goes_through_connect_design_and_run_to_a_running_bot(
    screen: _Screen,
) -> None:
    """`EPIC-034H`, on the composed app and the fake exchange: selecting a new
    bot reads its account and judges its plan by itself, the Plan lists the
    three steps done, and Save and start places the ladder."""
    app = screen.app
    bot_id = _created(app)
    screen.select(bot_id)

    screen.qtbot.waitUntil(
        lambda: _plan_says(screen, "Start: Ready to start"), timeout=_WAIT_MS
    )
    assert screen.view.plan.readiness_steps.text().splitlines() == [
        "1. Connect: done",
        "2. Design: done",
        "3. Run: done",
    ]

    screen.press(BotAction.START)
    screen.wait_for(bot_id, S.RUNNING)

    assert resting(app.urls) == ladder(app.runtime(bot_id))


def test_save_and_start_saves_the_edits_on_screen_and_starts_with_them(
    screen: _Screen,
) -> None:
    app = screen.app
    bot_id = _created(app)
    screen.select(bot_id)
    screen.qtbot.waitUntil(
        lambda: _plan_says(screen, "Start: Ready to start"), timeout=_WAIT_MS
    )
    panel = screen.view._kind_panel
    assert panel is not None
    panel.capital.setText("1500")
    panel.capital.textEdited.emit("1500")

    screen.press(BotAction.START)
    screen.wait_for(bot_id, S.RUNNING)

    assert app.bot(bot_id).definition.config["capital_quote"] == "1500"
    assert resting(app.urls) == ladder(app.runtime(bot_id))


def test_a_ladder_the_account_cannot_pay_for_is_listed_before_the_click_and_start_waits(
    screen: _Screen,
) -> None:
    """The balance is the exchange's snapshot (`BOT-174`): once the account holds
    less than the ladder spends, a refresh lists it on the Plan and holds Start
    off, with nothing placed."""
    app = screen.app
    bot_id = _created(app)
    screen.select(bot_id)
    screen.qtbot.waitUntil(
        lambda: _plan_says(screen, "Start: Ready to start"), timeout=_WAIT_MS
    )
    spot = app.urls.spot_account
    spot.withdraw_free("USDT", spot.free_balance("USDT") - Decimal(1500))

    screen.view.model.refresh_exchange_requested.emit()

    model = screen.view.model

    def balance_is_listed() -> bool:
        left = model.readiness
        return left is not None and "RUN_QUOTE_SHORT" in [
            item.code for item in left.items
        ]

    screen.qtbot.waitUntil(balance_is_listed, timeout=_WAIT_MS)
    assert "left" in screen.view.plan.readiness_header.text()
    assert "USDT free" in screen.view.plan.readiness_items.text()
    assert not screen.actions.action(lifecycle_id(BotAction.START)).isEnabled()
    assert resting(app.urls) == {}
