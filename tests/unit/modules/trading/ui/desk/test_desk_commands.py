"""`EPIC-033D` — a desk's Enable live trading and Emergency stop are actions.

The commands the trading module really contributes (`real_contributions`),
and the actions one desk's presenter binds (`desk_actions.py`): enabled while
the session can take a toggle, checked while trading is on, Emergency stop
only after its confirmation is accepted.
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_commands import (
    emergency_stop_id,
    enable_trading_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.futures_desk_screen import (
    FUTURES_DESK_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.spot_desk_screen import (
    SPOT_DESK_ROUTE,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.conftest import real_contributions

from .desk_screen_fixtures import build_desk

FUTURES = TradingVenue.FUTURES_TESTNET
SPOT = TradingVenue.SPOT_TESTNET


def test_the_trading_module_contributes_each_desks_commands_to_its_own_mode() -> None:
    modes = {
        command.command_id: command.mode
        for command in real_contributions(Mock()).commands()
    }

    assert modes[enable_trading_id(FUTURES)] == FUTURES_DESK_ROUTE
    assert modes[emergency_stop_id(FUTURES)] == FUTURES_DESK_ROUTE
    assert modes[enable_trading_id(SPOT)] == SPOT_DESK_ROUTE
    assert modes[emergency_stop_id(SPOT)] == SPOT_DESK_ROUTE


def test_enable_is_disabled_while_a_toggle_is_in_flight(qtbot) -> None:
    desk = build_desk(qtbot, FUTURES)
    enable = desk.actions.enable_trading

    desk.presenter.desk.set_trading_state(enabled=False, busy=True)
    assert not enable.isEnabled()

    desk.presenter.desk.set_trading_state(enabled=True, busy=False)
    assert enable.isEnabled()
    assert enable.isChecked()


def test_a_declined_emergency_stop_stops_nothing(qtbot) -> None:
    desk = build_desk(qtbot, SPOT)
    desk.session.set_enabled(enabled=True)
    desk.actions.confirmer.answer = False

    desk.actions.emergency_stop.trigger()

    assert len(desk.actions.confirmer.asked) == 1
    assert desk.session.emergency_stops == 0
    assert desk.session.snapshot().enabled is True


def test_emergency_stop_says_what_it_closes_on_each_market(qtbot) -> None:
    futures, spot = build_desk(qtbot, FUTURES), build_desk(qtbot, SPOT)

    futures.actions.emergency_stop.trigger()
    spot.actions.emergency_stop.trigger()

    (futures_asked,) = futures.actions.confirmer.asked
    (spot_asked,) = spot.actions.confirmer.asked
    assert "every position is closed" in futures_asked.consequence
    assert "sold at market" in spot_asked.consequence
    assert futures_asked.accept_text == spot_asked.accept_text == "Stop everything"
