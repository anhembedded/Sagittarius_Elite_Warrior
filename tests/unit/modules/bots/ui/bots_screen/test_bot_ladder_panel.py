"""`BOT-193` - the Ladder panel of the Bots mode shows the selected bot's grids from its saved record.

@details Driven through the presenter's real wiring (select a bot, settle the reads), so the
panel's rows are what `DetailEffects.refresh` hands the view model and not what a test fills in.
The words and figures are `grid_ladder.py`'s and `grid_ladder_texts.py`'s own tests; this file holds
what the screen adds: the dock follows the selection, a figure without a source is a blank cell and
never a zero, and a bot without a ladder says why.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtWidgets import QLabel, QTableView
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import (
    RUN_DIFFERS_NOTE,
    GridLadder,
    LadderUnavailable,
    grid_ladder_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder_texts import (
    LIQUIDATION_NOT_SAVED,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
    LevelOrder,
    RuntimeLevel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_ladder_facts import (
    NO_LADDER_YET,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_table_models import (
    BotLadderTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import displayed_text

from .bots_screen_fixtures import GOOD_CONFIG, BotsScreen, stored


def _select(screen: BotsScreen, bot_id: str) -> None:
    screen.settle()  # the list is read before a bot can be picked
    screen.view.model.select_requested.emit(bot_id)
    screen.settle()


def _text(screen: BotsScreen, row: int, key: str) -> str:
    view = screen.view.findChild(QTableView, "tblBotLadder")
    return displayed_text(view, row, BotLadderTableModel.column(key))


def _run(*resting: tuple[int, OrderSide, str]) -> dict[str, object]:
    """A saved Grid runtime of the 60000-70000 ladder with `resting` orders (level, side, price)."""
    orders = {level: (side, Decimal(price)) for level, side, price in resting}
    levels = tuple(
        RuntimeLevel(
            index,
            Decimal(60000 + 1000 * index),
            Decimal("0.01"),
            LevelState.RESTING if index in orders else LevelState.EMPTY,
            LevelOrder(f"c{index}", orders[index][0], orders[index][1], Decimal(1))
            if index in orders
            else None,
        )
        for index in range(11)
    )
    runtime = GridRuntime(
        levels,
        realised_profit=Decimal("12.5"),
        completed_cycles=5,
        mark_price=Decimal(64500),
        mark_price_at=datetime(2026, 10, 19, tzinfo=UTC),
    )
    return dict(encode_runtime(runtime))


def _fact(screen: BotsScreen, key: str) -> str:
    return screen.view.plan.facts.value_text(key)


def _running(runtime: dict[str, object]) -> StoredBot:
    return dataclasses.replace(stored("a00001", S.RUNNING), runtime=runtime)


def test_a_selected_grid_bot_shows_one_row_per_grid_from_its_saved_parameters(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.RUNNING)])

    _select(screen, "a00001")

    ladder = screen.view.model.ladder
    assert isinstance(ladder, GridLadder)
    rows = screen.view.ladder.grids.rows
    assert len(rows) == int(GOOD_CONFIG["grid_count"])
    assert (rows[0].buy, rows[-1].sell) == (Decimal(60000), Decimal(70000))
    assert _text(screen, 0, "step") == "1.67%"
    assert _text(screen, 9, "step") == "1.45%"


def test_what_is_not_known_is_a_blank_cell_never_a_zero(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.RUNNING)])

    _select(screen, "a00001")

    assert _text(screen, 0, "net") == ""
    assert _text(screen, 0, "net_quote") == ""
    assert _text(screen, 0, "gross_quote") != ""
    assert _text(screen, 0, "state") == "Not recorded"
    assert screen.view.ladder.summary.text().endswith("before fees (estimate)")
    assert "no maker rate is recorded" in screen.view.ladder.summary.toolTip()
    assert _fact(screen, "last_price") == "no price yet"
    assert _fact(screen, "cycle_average") == "—"
    assert _fact(screen, "cycle_profit").endswith("before fees")


def test_the_columns_say_where_each_figure_comes_from() -> None:
    columns = {spec.key: spec.title for spec in BotLadderTableModel.COLUMNS}

    assert "(designed)" in columns["step"]
    assert "(designed)" in columns["net"]
    assert "(estimate)" in columns["gross_quote"]
    assert "(estimate)" in columns["net_quote"]
    assert "(recorded)" in columns["state"]


def test_the_saved_runs_resting_orders_say_what_each_grid_is_doing(
    open_bots_screen,
) -> None:
    screen = open_bots_screen(
        [
            _running(
                _run((4, OrderSide.BUY, "64000"), (6, OrderSide.SELL, "66000")),
            )
        ]
    )
    _select(screen, "a00001")

    assert _text(screen, 4, "state") == "Waiting to buy"
    assert _text(screen, 5, "state") == "Waiting to sell"
    assert _text(screen, 0, "state") == "No order"


def test_the_plan_says_where_the_last_price_the_bot_heard_stands(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([_running(_run())])

    _select(screen, "a00001")

    assert _fact(screen, "last_price").startswith("64,500.00")
    assert _fact(screen, "lower_edge") == "60,000.00 (-6.98%)"
    assert _fact(screen, "upper_edge") == "70,000.00 (+8.53%)"
    assert _fact(screen, "stop_loss") == "off"
    assert _fact(screen, "take_profit") == "off"
    assert _fact(screen, "grid_step") == "1.45% to 1.67%"
    assert _fact(screen, "cycle_average").startswith("2.50")
    assert not screen.view.plan.facts.findChild(
        QLabel, "readout::liquidation"
    ).isVisibleTo(screen.view.plan)


def test_a_run_of_another_ladder_says_so_and_shows_no_state(open_bots_screen) -> None:
    screen = open_bots_screen([_running(_run((4, OrderSide.BUY, "12345")))])
    _select(screen, "a00001")

    assert screen.view.ladder.note.text() == RUN_DIFFERS_NOTE
    assert _text(screen, 3, "state") == "Not recorded"


def test_a_bot_whose_parameters_make_no_ladder_says_why_and_shows_no_rows(
    open_bots_screen,
) -> None:
    screen = open_bots_screen(
        [stored("b00002", S.DRAFT, config={"lower": "60000"}, name="no range")]
    )

    _select(screen, "b00002")

    assert isinstance(screen.view.model.ladder, LadderUnavailable)
    assert "upper is missing" in screen.view.ladder.summary.text()
    assert screen.view.ladder.grids.rows == ()


def test_with_no_bot_selected_the_panel_holds_its_instruction(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    _select(screen, "a00001")

    _select(screen, "")

    assert screen.view.ladder.summary.text() == NO_LADDER_YET
    assert screen.view.ladder.grids.rows == ()


def test_a_futures_bot_says_its_liquidation_price_is_not_in_the_record(qapp) -> None:
    now = datetime(2026, 10, 19, tzinfo=UTC)
    bot = dataclasses.replace(
        stored(
            "f00001", S.RUNNING, {**GOOD_CONFIG, "direction": "LONG", "leverage": "2"}
        ),
        runtime={},
    ).bot
    snapshot = BotSnapshot.of(
        dataclasses.replace(
            bot,
            definition=dataclasses.replace(
                bot.definition, venue=TradingVenue.FUTURES_TESTNET
            ),
        )
    )
    view = BotsView()

    view.model.set_selected(snapshot)
    view.model.set_ladder(grid_ladder_of(snapshot, now))

    row = view.plan.facts.findChild(QLabel, "readout::liquidation")
    assert row is not None and row.isVisibleTo(view.plan.facts)
    assert row.text() == LIQUIDATION_NOT_SAVED
    view.model.set_ladder(None)
    assert not row.isVisibleTo(view.plan.facts)
    view.deleteLater()
