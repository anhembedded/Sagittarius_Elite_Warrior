"""`EPIC-025` PR 1.4c-4 — the first widget a bounded context owns.

Against the module's own verified fake (`FakeTradingSession`), not a `Mock`:
HLD §10.3 rule 4 asks for exactly that when a test needs a port's behaviour,
and here it buys the assertion that matters — `snapshot_reads`, which is how
this file can say the probe reads the session **once** per refresh rather than
three times for three labels.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    TradingSessionSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.session_probe import (
    TradingSessionProbe,
)


def _snapshot(
    *,
    enabled: bool = False,
    orders_sent: int = 0,
    symbols: frozenset[str] = frozenset(),
) -> TradingSessionSnapshot:
    return TradingSessionSnapshot(
        enabled=enabled,
        orders_sent_this_session=orders_sent,
        known_open_symbols=symbols,
    )


def test_it_shows_the_session_state_as_soon_as_it_is_built(qapp) -> None:
    """A probe opened mid-session must answer immediately: a developer opens
    it *because* they want the current numbers, and an empty panel until they
    press Refresh reads as "the session is empty"."""
    session = FakeTradingSession(
        _snapshot(enabled=True, orders_sent=3, symbols=frozenset({"BTCUSDT"}))
    )

    probe = TradingSessionProbe(session)

    assert probe._enabled.text() == "ON"
    assert probe._orders_sent.text() == "3"
    assert probe._open_symbols.text() == "BTCUSDT"


def test_live_submission_off_says_so_rather_than_showing_nothing(qapp) -> None:
    probe = TradingSessionProbe(FakeTradingSession(_snapshot(enabled=False)))

    assert probe._enabled.text() == "OFF"


def test_no_open_symbols_reads_as_a_dash_not_an_empty_line(qapp) -> None:
    """An empty label is indistinguishable from a broken one."""
    probe = TradingSessionProbe(FakeTradingSession(_snapshot()))

    assert probe._open_symbols.text() == "—"


def test_the_symbols_are_sorted_so_the_line_is_stable(qapp) -> None:
    """A `frozenset`'s iteration order is not the user's: without the sort the
    same state renders differently between runs, and a developer comparing two
    screenshots would read that as a change."""
    probe = TradingSessionProbe(
        FakeTradingSession(_snapshot(symbols=frozenset({"ETHUSDT", "BTCUSDT"})))
    )

    assert probe._open_symbols.text() == "BTCUSDT, ETHUSDT"


def test_refresh_reads_the_session_again(qapp) -> None:
    session = FakeTradingSession(_snapshot(orders_sent=1))
    probe = TradingSessionProbe(session)

    session.answer_with(_snapshot(enabled=True, orders_sent=2))
    probe.refresh()

    assert probe._enabled.text() == "ON"
    assert probe._orders_sent.text() == "2"


def test_the_refresh_button_is_what_refreshes_it(qapp) -> None:
    session = FakeTradingSession(_snapshot(orders_sent=1))
    probe = TradingSessionProbe(session)
    session.answer_with(_snapshot(orders_sent=9))

    probe._refresh_button.click()

    assert probe._orders_sent.text() == "9"


def test_one_refresh_is_one_read_of_the_session(qapp) -> None:
    """Three labels, one `snapshot()`: the session takes its lock once, so the
    three values on screen are a combination that actually existed. Three
    reads could show a count from before an order and a symbol set from after
    it (`domain-truth-rule.md`)."""
    session = FakeTradingSession(_snapshot())

    probe = TradingSessionProbe(session)

    assert session.snapshot_reads == 1

    probe.refresh()

    assert session.snapshot_reads == 2


def test_it_never_asks_the_session_to_do_anything(qapp) -> None:
    """A probe reports. Enabling trading from a dev panel would be a second
    way to arm the most dangerous switch in the app, next to the one the user
    knows about."""
    session = FakeTradingSession(_snapshot())

    TradingSessionProbe(session).refresh()

    assert (session.enables, session.disables, session.emergency_stops) == (0, 0, 0)
