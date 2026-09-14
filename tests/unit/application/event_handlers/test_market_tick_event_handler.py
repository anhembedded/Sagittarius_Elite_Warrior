"""`MarketTickEventHandler` is an adapter, and these tests hold it to that.

`EPIC-022A` moved the symbol/interval filtering, the `on_tick()` call and
the hand-off to `LiveTradingCoordinator` into `LiveStrategySession`, so
the assertions that used to live here (including `BUG-085`'s
interleaved-interval regressions) moved with them, to
`tests/unit/application/services/test_live_strategy_session.py`. What
stays here is what this class still owns: log level, and delegating every
tick to the session unfiltered.
"""

from datetime import UTC, datetime
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.event_handlers.market_data.market_tick_event_handler import (
    MarketTickEventHandler,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.domain.events.market_tick_event import (
    MarketTickEvent,
)


def _market_data(
    symbol: str = "BTCUSDT", interval: str = TimeFrame.ONE_MINUTE.value
) -> MarketData:
    dt = datetime(2023, 1, 1, tzinfo=UTC)
    return MarketData(
        symbol=symbol,
        interval=interval,
        open_time=dt,
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=105.0,
        volume=1000.0,
        close_time=dt,
        quote_asset_volume=105000.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=52500.0,
    )


def test_logs_at_debug_not_info():
    """`EPIC-021G` §2.5 / `BUG-042`: tick processing runs every candle,
    every symbol — it must never be `INFO`, or `SignalLogHandler` mirrors
    it to the UI's queued log model on every single tick."""
    handler = MarketTickEventHandler(Mock())
    handler.logger = Mock()

    handler.handle(MarketTickEvent(market_data=_market_data()))

    handler.logger.debug.assert_called_once()
    handler.logger.info.assert_not_called()
    call_args = handler.logger.debug.call_args[0][0]
    assert "Processing tick for" in call_args
    assert "BTCUSDT" in call_args


def test_every_tick_is_handed_to_the_session_unfiltered():
    """The handler deliberately does NOT pre-filter by symbol/interval:
    `LiveStrategySession` owns that decision because it is the only place
    that can read the armed config and the engine as one consistent
    snapshot (`EPIC-022A`). A handler that filtered too would be a second
    copy of the rule, free to disagree with the first."""
    session = Mock()
    handler = MarketTickEventHandler(session)
    event = MarketTickEvent(market_data=_market_data("ETHUSDT"))

    handler.handle(event)

    session.dispatch_tick.assert_called_once_with(event.market_data)
