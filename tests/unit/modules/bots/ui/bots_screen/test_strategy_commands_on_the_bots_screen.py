"""`EPIC-033K` stage 3, `BOT-219` — the Bots screen, built as the app builds it, arms a strategy
from Bots → Arm strategy… and disarms it from Disarm strategy…, with no Strategies panel.

What `test_venue_strategies.py` proves of the commands is proven there; this file proves the
wiring `BotsPresenter` does: the commands read the container's venues, are bound to them, ask the
screen's own questions (`BotsDialogs.ask_arm_strategy`, `choose_venue`), and an
`ArmedStrategyChangedEvent` arriving on the bus is told in the Bots channel of the Output pane.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDockWidget
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    ARM_STRATEGY,
    DISARM_STRATEGY,
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


def _told(screen) -> list[str]:
    log = screen.view.output_log
    return [log.index(row).data(log.MessageRole) for row in range(log.rowCount())]


def test_the_screen_has_no_strategies_dock_and_offers_arm_but_not_disarm(
    open_bots_screen,
) -> None:
    screen = open_bots_screen()

    titles = {d.windowTitle() for d in screen.view.surface.findChildren(QDockWidget)}
    assert "Strategies" not in titles
    assert screen.actions.action(ARM_STRATEGY).isEnabled()
    assert not screen.actions.action(DISARM_STRATEGY).isEnabled()


def test_arm_strategy_asks_the_screen_what_and_where_and_arms_that_venue(
    open_bots_screen,
) -> None:
    screen = open_bots_screen(answers=Answers(arm_strategy=True))
    arm = screen.actions.action(ARM_STRATEGY)

    arm.trigger()

    assert screen.answers.asked[0].startswith("arm ")
    armed_with = screen.strategy.arming.armed_with
    assert armed_with is not None and armed_with.strategy_key == STRATEGY_KEY
    assert screen.actions.action(DISARM_STRATEGY).isEnabled()


def test_disarm_strategy_disarms_the_one_armed_venue_without_asking(
    open_bots_screen,
) -> None:
    screen = open_bots_screen(answers=Answers(arm_strategy=True))
    screen.actions.action(ARM_STRATEGY).trigger()
    asked = len(screen.answers.asked)

    screen.actions.action(DISARM_STRATEGY).trigger()

    assert screen.strategy.arming.disarm_calls == 1
    assert len(screen.answers.asked) == asked  # one venue armed: nothing to choose


def test_an_arming_announced_on_the_bus_is_told_in_the_bots_channel_of_the_output_pane(
    open_bots_screen, qapp
) -> None:
    screen = open_bots_screen()
    screen.strategy.armed.seed(
        LiveStrategyConfig(strategy_key=STRATEGY_KEY, symbol="BTCUSDT", interval="1m")
    )

    screen.bus.emit(ArmedStrategyChangedEvent(True, venue=VENUE))
    qapp.processEvents()

    (line,) = _told(screen)
    assert line.startswith(f"Strategy armed on {VENUE.display_name}: ")
    assert "BTCUSDT 1m" in line
    assert screen.view.output_channel() is not None
    assert screen.view.output_channel().channel_id == "bots"


def test_an_open_order_session_does_not_wait_the_arm_command(
    open_bots_screen, qapp
) -> None:
    """`EPIC-034C` — arming no longer needs the venue's trading off: a session a
    bot, an order or an earlier arm opened leaves the command as it was."""
    screen = open_bots_screen()
    arm = screen.actions.action(ARM_STRATEGY)
    assert arm.isEnabled()
    screen.trading_session.set_enabled(enabled=True)

    screen.bus.emit(
        TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=VENUE)
    )
    qapp.processEvents()

    assert arm.isEnabled()
