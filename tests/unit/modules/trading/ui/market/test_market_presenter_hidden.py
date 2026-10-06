"""`BOT-165`: leaving the Market mode releases the Watchlist's own stream and
coming back starts it again; nothing a restore does changes (`BUG-104`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.watchlist_stream import (
    WATCHLIST_STREAM_OWNER,
)

_SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT")


def _live(build, stream: FakeMarketStream):
    presenter = build(stream=stream)
    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    return presenter


def test_leaving_the_mode_stops_the_watchlist_owner(build):
    stream = FakeMarketStream()
    presenter = _live(build, stream)

    presenter.on_mode_hidden()

    assert stream.held_by(WATCHLIST_STREAM_OWNER) is None
    assert "paused" in presenter.view.stream.text()


def test_returning_starts_the_watchlist_again(build):
    stream = FakeMarketStream()
    presenter = _live(build, stream)
    presenter.on_mode_hidden()

    presenter.on_mode_shown(NavigationSource.USER_INTENT)

    held = stream.held_by(WATCHLIST_STREAM_OWNER)
    assert held is not None
    assert held.symbols == _SYMBOLS
    assert presenter.view.stream.text() == "Market data: live"


def test_a_click_on_the_showing_mode_does_not_restart_the_stream(build):
    stream = FakeMarketStream()
    presenter = _live(build, stream)

    presenter.on_mode_shown(NavigationSource.USER_INTENT)

    assert stream.calls == [("start", WATCHLIST_STREAM_OWNER)]


def test_another_owners_stream_of_the_same_symbol_survives_the_leave(build):
    stream = FakeMarketStream()
    presenter = _live(build, stream)
    stream.start("bot.grid", MarketType.SPOT, ["BTCUSDT"], TimeFrame.ONE_MINUTE)

    presenter.on_mode_hidden()

    assert stream.held_by("bot.grid") is not None
    assert stream.is_streaming("BTCUSDT")
    assert ("stop", "bot.grid") not in stream.calls


def test_hiding_a_mode_that_never_went_live_stops_nothing(build):
    stream = FakeMarketStream()
    presenter = build(stream=stream)
    presenter.on_mode_shown(NavigationSource.RESTORE)

    presenter.on_mode_hidden()
    presenter.on_mode_shown(NavigationSource.RESTORE)

    assert stream.calls == []


def test_a_market_switch_while_hidden_starts_nothing(build):
    stream = FakeMarketStream()
    presenter = _live(build, stream)
    presenter.on_mode_hidden()

    presenter._on_market_changed(MarketType.FUTURES_USD_M)

    assert stream.held_by(WATCHLIST_STREAM_OWNER) is None
