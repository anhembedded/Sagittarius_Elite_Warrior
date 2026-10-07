"""`BUG-172` — a chart opened at rest on an empty store fetches its history.

@details The owner's Futures Testnet desk chart stayed empty: opened at rest it only
read the local store, found nothing, fetched nothing and said so in a log line. With
candles stored it still goes on no network (`test_live_chart_coordinator.py`); with
none it syncs its venue's market, reads again, and says why in words when the
exchange has none either. Driven synchronously over the verified fakes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_coordinator import (
    LiveChartCoordinator,
)
from Sagittarius_Elite_Warrior.tests.unit.support.charting.live_chart.live_chart_fixtures import (
    silent_callbacks,
)


class _FakeToken:
    def is_cancelled(self) -> bool:
        return False


def _coordinator(
    sync: FakeMarketDataSync,
    history: FakeHistoricalKlines,
    stream: FakeMarketStream | None = None,
) -> LiveChartCoordinator:
    feed = MarketDataCandleFeed(
        sync, history, stream or FakeMarketStream(), MarketType.SPOT
    )
    callbacks = silent_callbacks()
    return LiveChartCoordinator(MagicMock(), feed, callbacks, "desk.spot_testnet")


class _SeedingSync(FakeMarketDataSync):
    """A sync that stores one candle, as a completed fetch would."""

    def __init__(self, history: FakeHistoricalKlines, rows: int = 1) -> None:
        super().__init__()
        self._history = history
        self._rows = rows

    def sync(self, request) -> None:
        super().sync(request)
        self._history.seed([candle("BTCUSDT", n) for n in range(self._rows)])


def test_an_empty_store_is_fetched_then_read_and_still_opens_no_stream() -> None:
    """`BUG-172` — a desk or bot chart opened at rest on an empty store drew
    nothing and said so only in a log line. It fetches the history from its
    venue's market, reads again and draws it; a fetch is a read of public candles,
    so no stream is opened."""
    history = FakeHistoricalKlines()
    sync = _SeedingSync(history)
    stream = FakeMarketStream()
    coordinator = _coordinator(sync, history, stream)
    history_ready = coordinator._callbacks.history_ready

    coordinator._run("BTCUSDT", "1m", _FakeToken(), False)

    assert [r.symbols for r in sync.requests] == [("BTCUSDT",)]
    assert history_ready.call_args.args[3], "the fetched candles were drawn"
    assert stream.calls == [], "fetching history opens no live stream"


def test_an_empty_store_that_stays_empty_says_why_in_words() -> None:
    """A chart with no candles must never be shown silently (`BUG-172`): the
    exchange had none for the period (a testnet keeps a short history)."""
    history = FakeHistoricalKlines()
    coordinator = _coordinator(FakeMarketDataSync(), history)
    callbacks = coordinator._callbacks

    coordinator._run("BTCUSDT", "1m", _FakeToken(), False)

    headline = callbacks.load_failed.call_args.args[1]
    assert "no 1m candles of BTCUSDT" in headline
    assert callbacks.history_ready.call_args.args[3] == [], "the empty window is drawn"


def test_an_empty_store_whose_fetch_fails_tells_it_and_draws_the_empty_window() -> None:
    class _Down(FakeMarketDataSync):
        def sync(self, request) -> None:
            raise OSError("no route")

    coordinator = _coordinator(_Down(), FakeHistoricalKlines())
    callbacks = coordinator._callbacks

    coordinator._run("BTCUSDT", "1m", _FakeToken(), False)

    assert "Could not sync BTCUSDT" in callbacks.load_failed.call_args.args[1]
    assert callbacks.history_ready.call_args.args[3] == []


def test_the_fetch_is_bounded_to_the_charts_window() -> None:
    """At `1s` the default depth (30 days) is about 2.6 million candles for a chart
    that draws 500; the at-rest fetch asks for the newest 500 only."""
    history = FakeHistoricalKlines()
    sync = _SeedingSync(history)
    coordinator = _coordinator(sync, history)

    coordinator._run("BTCUSDT", "1s", _FakeToken(), False)

    (request,) = sync.requests
    assert request.start_time is not None
    window = datetime.now(UTC) - request.start_time
    assert abs(window.total_seconds() - 500) < 60, window


def test_a_failed_fetch_at_rest_does_not_fail_the_stream() -> None:
    """Retry of a stream failure goes live; an empty store at rest has no stream to
    retry, so its failure is a load failure (`BUG-172`)."""
    coordinator = _coordinator(FakeMarketDataSync(), FakeHistoricalKlines())
    callbacks = coordinator._callbacks

    coordinator._run("BTCUSDT", "1m", _FakeToken(), False)

    callbacks.stream_failed.assert_not_called()
    callbacks.load_failed.assert_called_once()
