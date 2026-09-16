"""The candle series every Dev Board integration test reads.

**Why this is not in `conftest.py`.** A test module that needs these has to
import them, and importing `conftest` by name executes that file a *second*
time under a second module identity — pytest has already loaded it as a
plugin. `EPIC-025` PR 1.1a's cleanup did exactly that and the whole
`integration/presentation/ui` tier stopped being able to finish: the second
copy of the conftest module aborted the interpreter mid-run (`Fatal Python
error: Aborted` inside a worker thread while the main thread collected
garbage — the same shape `conftest._FakeResponse` documents).

A plain module is not a plugin, so importing it is just an import. The
builder lives here, `conftest.py` imports it like anyone else, and there is
one source for the series instead of the copy that used to sit in
`test_dev_board_load_more.py` and had already drifted two years out of date.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData

#: How many candles one page of mocked history holds. Shared so it never
#: silently drifts between the files that assert on it.
MOCK_KLINE_COUNT = 5

#: Every symbol the seeded history answers for. The Dev Board tests drive the
#: symbol dropdown, so the fake must hold rows for each option they can pick —
#: a dispatch stub answered for whatever it was asked; a store only answers
#: for what was put in it.
SEEDED_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT")


#: The one instant this module's grid hangs from, read **once per process**
#: (`BUG-123`). It used to be `datetime.now()` inside the builder, so every
#: call got its own grid: the store was seeded in a fixture, the load-more
#: tests derived "the page below what the screen shows" from a second call in
#: the test body, and a minute rolling over between the two shifted that
#: second grid one minute later. The older page's newest row then landed
#: exactly on the row the chart already held, the store deduplicated it, and 4
#: of 5 candles were new — a failure that needed no code change to appear or
#: disappear, only a clock. The same read also put the five seeded symbols on
#: five different grids, which nothing was watching at all.
#:
#: Freezing it at import keeps both properties the clock was read for: the
#: series stays inside any recent-window default, and it only ever gets
#: *older* as the session runs, so it never claims a candle from the future.
_SERIES_ANCHOR = datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(
    minutes=MOCK_KLINE_COUNT
)


def build_mock_klines(symbol: str, interval: str = "1m") -> list[MarketData]:
    """Newest-first `MarketData` list, matching what the real repository
    returns (DashboardPresenter reverses it before rendering).

    **Anchored to the clock, and `EPIC-025` PR 1.1a is why.** These rows used
    to sit at a fixed `2024-01-01`, which worked because the dispatch stub
    answering the klines query ignored `start_time`/`end_time` entirely and
    handed the list back whatever was asked. `IHistoricalKlines` reads a store,
    and a store honours the range — so rows two years outside the Data Range
    picker's own default window are correctly filtered to nothing, and every
    Dev Board history test went quiet. Ending one minute in the past keeps the
    series inside any recent-window default while never claiming a candle from
    the future.

    **One anchor, not one per call** — see `_SERIES_ANCHOR` and `BUG-123`.
    Every caller in a process gets the same grid, which is what lets one
    caller build a page adjacent to what another caller stored.
    """
    base_time = _SERIES_ANCHOR
    klines = [
        MarketData(
            symbol=symbol,
            interval=interval,
            open_time=base_time + timedelta(minutes=i),
            open_price=100.0 + i,
            high_price=101.0 + i,
            low_price=99.0 + i,
            close_price=100.5 + i,
            volume=10.0,
            close_time=base_time + timedelta(minutes=i + 1),
            quote_asset_volume=1000.0,
            number_of_trades=5,
            taker_buy_base_asset_volume=5.0,
            taker_buy_quote_asset_volume=500.0,
        )
        for i in range(MOCK_KLINE_COUNT)
    ]
    klines.reverse()
    return klines
