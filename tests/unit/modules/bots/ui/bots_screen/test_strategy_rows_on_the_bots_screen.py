"""`EPIC-033K` stage 3 — the Bots screen, built as the app builds it, lists
each served venue's strategy and arms it from Bots → Arm strategy….

What `test_venue_strategies.py` proves of the rows is proven there; this
file proves the wiring `BotsPresenter` does: the rows read the container's
venues, the two commands are bound to them, the question is the screen's
own (`BotsDialogs.ask_arm_strategy`), and the rows follow an
`ArmedStrategyChangedEvent` arriving on the bus.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    ARM_STRATEGY,
    DISARM_STRATEGY,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.strategy_rows import (
    ARMED_TEXT,
    StrategyRow,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.armed_strategy_changed_event import (
    ArmedStrategyChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)

from ..strategies.strategy_fakes import STRATEGY_KEY
from .bots_screen_fixtures import VENUE, Answers


def _rows(screen) -> tuple[StrategyRow, ...]:
    return screen.view.strategies.model.rows


def _select_the_venue(screen) -> None:
    table = screen.view.strategies.table
    assert table.select_first(lambda row: row.venue is VENUE)


def test_the_screen_lists_each_served_venue_and_waits_for_a_selection(
    open_bots_screen,
) -> None:
    screen = open_bots_screen()

    assert [row.venue for row in _rows(screen)] == [VENUE]
    assert not screen.actions.action(ARM_STRATEGY).isEnabled()
    assert not screen.actions.action(DISARM_STRATEGY).isEnabled()


def test_arm_strategy_asks_the_screen_and_arms_the_selected_venue(
    open_bots_screen,
) -> None:
    screen = open_bots_screen(answers=Answers(arm_strategy=True))
    _select_the_venue(screen)
    arm = screen.actions.action(ARM_STRATEGY)
    assert arm.isEnabled()

    arm.trigger()

    assert screen.answers.asked == [f"arm {VENUE.value}"]
    armed_with = screen.strategy.arming.armed_with
    assert armed_with is not None and armed_with.strategy_key == STRATEGY_KEY
    assert _rows(screen)[0].armed
    assert screen.actions.action(DISARM_STRATEGY).isEnabled()
    assert not arm.isEnabled()


def test_the_rows_follow_an_arming_announced_on_the_bus(open_bots_screen, qapp) -> None:
    screen = open_bots_screen()
    screen.strategy.armed.seed(
        LiveStrategyConfig(strategy_key=STRATEGY_KEY, symbol="BTCUSDT", interval="1m")
    )

    screen.bus.emit(ArmedStrategyChangedEvent(True, venue=VENUE))
    qapp.processEvents()

    row = _rows(screen)[0]
    assert row.armed and "BTCUSDT 1m" in row.summary
    table = screen.view.strategies.table
    assert table.text(0, screen.view.strategies.model.column("state")) == ARMED_TEXT


def test_an_open_order_session_does_not_wait_the_arm_command(
    open_bots_screen, qapp
) -> None:
    """`EPIC-034C` — arming no longer needs the venue's trading off: a session a
    bot, an order or an earlier arm opened leaves the command as it was."""
    screen = open_bots_screen()
    _select_the_venue(screen)
    arm = screen.actions.action(ARM_STRATEGY)
    assert arm.isEnabled()
    screen.trading_session.set_enabled(enabled=True)

    screen.bus.emit(
        TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=VENUE)
    )
    qapp.processEvents()

    assert arm.isEnabled()
