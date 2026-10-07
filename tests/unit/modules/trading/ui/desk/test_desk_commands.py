"""`EPIC-033D`, `EPIC-033I` — the Trade mode's Emergency stop, on one desk.

The actions the mode binds to the venue chosen (`desk_actions.py`): Emergency
stop only after its confirmation is accepted (`EPIC-034C` removed Enable live
trading). What the module contributes is `trade/test_trade_commands.py`'s.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .desk_screen_fixtures import build_desk

FUTURES = TradingVenue.FUTURES_TESTNET
SPOT = TradingVenue.SPOT_TESTNET


def test_a_declined_emergency_stop_stops_nothing(qtbot) -> None:
    desk = build_desk(qtbot, SPOT)
    desk.session.set_enabled(enabled=True)
    desk.actions.confirmer.answer = False

    desk.actions.emergency_stop.trigger()

    assert len(desk.actions.confirmer.asked) == 1
    assert desk.session.emergency_stops == 0
    assert desk.session.snapshot().enabled is True


def test_emergency_stop_says_what_it_closes_on_the_desks_market(qtbot) -> None:
    futures, spot = build_desk(qtbot, FUTURES), build_desk(qtbot, SPOT)

    futures.actions.emergency_stop.trigger()
    spot.actions.emergency_stop.trigger()

    (futures_asked,) = futures.actions.confirmer.asked
    (spot_asked,) = spot.actions.confirmer.asked
    assert "every Futures position is closed" in futures_asked.consequence
    assert "sold at market" in spot_asked.consequence
    assert futures_asked.accept_text == spot_asked.accept_text == "Stop everything"
    assert futures.session.emergency_stops == spot.session.emergency_stops == 1
