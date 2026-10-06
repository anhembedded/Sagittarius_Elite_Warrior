"""`EPIC-033I` — one Trade mode for both venues: the venue chosen on the
toolbar shows its page and receives the mode's commands; Emergency stop
stops every venue; a run with no venue enabled says so and sends nothing.

Over verified fakes (`trade_fixtures.py`): the real view, presenter and
desks, driven through the window's own actions.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_commands import (
    venue_choice_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_view import (
    NO_VENUE_TEXT,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from ..desk.desk_screen_fixtures import DeskSetup
from ..desk.futures_entry_fixtures import futures_status, futures_terms
from ..desk.order_entry_fixtures import TERMS, spot_status
from .trade_fixtures import build_trade

FUTURES = TradingVenue.FUTURES_TESTNET
SPOT = TradingVenue.SPOT_TESTNET
BOTH = (FUTURES, SPOT)


def test_each_enabled_venue_has_a_page_and_the_first_shows(qtbot) -> None:
    trade = build_trade(qtbot, BOTH)

    assert set(trade.presenter.desks) == set(BOTH)
    assert trade.view.shown_venue is FUTURES
    assert trade.action(venue_choice_id(FUTURES)).isChecked()
    assert not trade.action(venue_choice_id(SPOT)).isChecked()


def test_choosing_a_venue_shows_its_page_and_its_panels(qtbot) -> None:
    trade = build_trade(qtbot, BOTH)

    trade.choose(SPOT)

    assert trade.view.shown_venue is SPOT
    assert trade.view.shown_surface() is trade.view.venue_page(SPOT).surface
    assert trade.action(venue_choice_id(SPOT)).isChecked()
    assert not trade.action(venue_choice_id(FUTURES)).isChecked()


def test_enable_reaches_the_chosen_venue_only(qtbot) -> None:
    trade = build_trade(qtbot, BOTH)

    trade.choose(SPOT)
    trade.enable_trading.trigger()

    assert trade.fakes[SPOT].session.enables == 1
    assert trade.fakes[FUTURES].session.enables == 0

    trade.choose(FUTURES)
    trade.enable_trading.trigger()

    assert trade.fakes[FUTURES].session.enables == 1
    assert trade.fakes[SPOT].session.enables == 1


def test_enable_shows_the_chosen_venues_state(qtbot) -> None:
    """Trading on for Spot only: Enable reads checked on Spot, unchecked on
    Futures, whichever was chosen last."""
    trade = build_trade(qtbot, BOTH)
    trade.choose(SPOT)
    trade.enable_trading.trigger()
    assert trade.enable_trading.isChecked()

    trade.choose(FUTURES)
    assert not trade.enable_trading.isChecked()

    trade.choose(SPOT)
    assert trade.enable_trading.isChecked()


def test_new_order_focuses_the_chosen_venues_entry(qtbot) -> None:
    trade = build_trade(
        qtbot,
        BOTH,
        {
            FUTURES: DeskSetup(
                account_snapshot=FakeAccountSnapshot(futures_status()),
                order_entry_terms=futures_terms(),
            ),
            SPOT: DeskSetup(
                account_snapshot=FakeAccountSnapshot(spot_status()),
                order_entry_terms=FakeOrderEntryTerms(TERMS),
            ),
        },
    )
    trade.view.show()
    qtbot.waitExposed(trade.view)
    trade.view.activateWindow()
    trade.choose(SPOT)
    assert trade.new_order.isEnabled()

    trade.new_order.trigger()

    spot_price = trade.view.venue_page(SPOT).findChild(QLineEdit, "txtPriceBuy")
    qtbot.waitUntil(lambda: QApplication.focusWidget() is spot_price)


def test_emergency_stop_asks_once_then_stops_every_venue(qtbot) -> None:
    trade = build_trade(qtbot, BOTH)
    for venue in BOTH:
        trade.fakes[venue].session.set_enabled(enabled=True)

    trade.emergency_stop.trigger()

    assert len(trade.confirmer.asked) == 1
    assert trade.fakes[FUTURES].session.emergency_stops == 1
    assert trade.fakes[SPOT].session.emergency_stops == 1


def test_a_declined_emergency_stop_stops_nothing(qtbot) -> None:
    trade = build_trade(qtbot, BOTH)
    trade.confirmer.answer = False

    trade.emergency_stop.trigger()

    assert trade.fakes[FUTURES].session.emergency_stops == 0
    assert trade.fakes[SPOT].session.emergency_stops == 0


def test_with_no_venue_enabled_the_mode_says_so_and_sends_nothing(qtbot) -> None:
    trade = build_trade(qtbot, ())

    notice = trade.view.findChild(QLabel, "lblNoVenue")
    assert notice is not None
    assert notice.text() == NO_VENUE_TEXT
    assert trade.view.shown_surface() is None
    assert trade.view.findChildren(QPushButton) == []
    assert trade.registry.unbound() == ()
    assert not trade.enable_trading.isEnabled()
    assert not trade.new_order.isEnabled()
    assert not trade.emergency_stop.isEnabled()


def test_one_venue_enabled_offers_that_venue_alone(qtbot) -> None:
    trade = build_trade(qtbot, (SPOT,))

    assert set(trade.presenter.desks) == {SPOT}
    assert trade.view.shown_venue is SPOT
    assert trade.enable_trading.isEnabled()
