"""`IHistoricalKlines`'s contract, against both implementations (HLD §10.3).

**Where the real half runs, and why here rather than `tests/integration/`.**
`StoredKlinesReader` holds no I/O of its own: it reads
`IMarketDataRepository`. Running it over `FakeMarketDataRepository` — itself a
verified fake with its own contract suite (PR 0.4a-3) — exercises the real
limit, ordering, range-filter and concurrency code paths with nothing to
integrate, so this tier can prove them (`ci-rule.md` §6 — the tier is chosen
by what the test touches, not by which class it names).

What that leaves for `tests/integration/` is SQLite's own behaviour: real
`ORDER BY`, real `LIMIT`, real timestamp comparison. `IMarketDataRepository`'s
suite already runs there against the real engine, which is where a divergence
between the in-memory store and SQL would surface.

**Why the real handler is composed here and not inside the fake.** The obvious
shortcut is to make `FakeHistoricalKlines` *be* the reader over a fake store,
which cannot diverge by construction — and would make `contracts/` depend on
`application/`, inverting a direction this module has never inverted. The
import costs nothing in a test file, so the composition lives here and
`contracts/` stays outward-facing.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_historical_klines.handler import (
    StoredKlinesReader,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    MINUTE,
    at,
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.contract_historical_klines import (
    HistoricalKlinesContract,
    SeedKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)


class TestFakeHistoricalKlines(HistoricalKlinesContract):
    """The fake's half — what every consumer's test will be driving."""

    @pytest.fixture
    def impl(self) -> IHistoricalKlines:
        return FakeHistoricalKlines()

    @pytest.fixture
    def seed(self, impl: IHistoricalKlines) -> SeedKlines:
        assert isinstance(impl, FakeHistoricalKlines)
        return impl.seed


class TestTheRealQueryHandler(HistoricalKlinesContract):
    """The real one's half — this is what makes the fake *verified*."""

    @pytest.fixture
    def store(self) -> FakeMarketDataRepository:
        return FakeMarketDataRepository()

    @pytest.fixture
    def impl(self, store: FakeMarketDataRepository) -> IHistoricalKlines:
        return StoredKlinesReader(store)

    @pytest.fixture
    def seed(self, store: FakeMarketDataRepository) -> SeedKlines:
        def put(klines: Sequence[MarketData]) -> None:
            store.save_klines(MarketType.SPOT, list(klines))

        return put


class TestTheFakesOwnQuery:
    """`was_read_for()` — the fake's own helper, not on the port.

    `BUG-120`'s guard requires this: the contract suite covers what
    `IHistoricalKlines` declares, and a helper the fake adds is covered by
    nobody unless its own module tests it. The two "no" cases are the ones
    that matter — a helper which can only say yes is the `Mock` it replaced.
    """

    def test_it_says_no_when_nothing_was_read(self) -> None:
        assert FakeHistoricalKlines().was_read_for("BTCUSDT") is False

    def test_it_says_no_for_a_symbol_nobody_asked_about(self) -> None:
        fake = FakeHistoricalKlines()

        fake.load("BTCUSDT", MINUTE)

        assert fake.was_read_for("ETHUSDT") is False

    def test_it_says_yes_for_a_symbol_that_was_read(self) -> None:
        fake = FakeHistoricalKlines()

        fake.load("BTCUSDT", MINUTE)

        assert fake.was_read_for("BTCUSDT") is True

    def test_a_read_with_nothing_stored_still_counts_as_a_read(self) -> None:
        """The distinction a consumer's test needs: "the chart asked" and "the
        chart got rows" are different facts, and a screen that asked for a
        symbol with no data has still asked."""
        fake = FakeHistoricalKlines()

        assert fake.load("BTCUSDT", MINUTE) == ()
        assert fake.was_read_for("BTCUSDT") is True

    def test_the_interval_narrows_the_answer(self) -> None:
        fake = FakeHistoricalKlines()

        fake.load("BTCUSDT", MINUTE)

        assert fake.was_read_for("BTCUSDT", MINUTE) is True
        assert fake.was_read_for("BTCUSDT", TimeFrame.ONE_DAY) is False

    def test_load_many_registers_every_symbol_it_was_given(self) -> None:
        fake = FakeHistoricalKlines()

        fake.load_many(["BTCUSDT", "ETHUSDT"], MINUTE)

        assert fake.was_read_for("BTCUSDT") is True
        assert fake.was_read_for("ETHUSDT") is True

    def test_reads_records_what_was_asked_for_in_order(self) -> None:
        """`reads` is the surface a consumer asserts "the chart asked for 500
        candles, not 5000" against — a fact about the screen, not the store."""
        fake = FakeHistoricalKlines()

        fake.load("BTCUSDT", MINUTE, limit=500, newest_first=True)
        fake.load_many(["ETHUSDT"], TimeFrame.ONE_DAY, limit=7)

        assert [
            (read.symbols, read.interval, read.limit, read.newest_first)
            for read in fake.reads
        ] == [
            (("BTCUSDT",), MINUTE, 500, True),
            (("ETHUSDT",), TimeFrame.ONE_DAY, 7, False),
        ]

    def test_a_read_records_the_range_it_was_bounded_by(self) -> None:
        """Dev Board asserts "the Data Range picker reached the read, and the
        sync was NOT given it" (`BUG-106`) — which needs the bounds on the
        record, not just the symbol and the limit."""
        fake = FakeHistoricalKlines()
        start, end = at(1), at(9)

        fake.load("BTCUSDT", MINUTE, start_time=start, end_time=end)

        assert fake.reads[0].start_time == start
        assert fake.reads[0].end_time == end

    def test_an_unbounded_read_records_no_range(self) -> None:
        fake = FakeHistoricalKlines()

        fake.load("BTCUSDT", MINUTE)

        assert fake.reads[0].start_time is None
        assert fake.reads[0].end_time is None


def test_the_fake_and_the_handler_agree_on_a_seeded_series() -> None:
    """One belt-and-braces check outside the suite: the same rows, read both
    ways, come back identical. The suite already pins every promise
    separately; this catches a divergence in something the suite did not think
    to name."""
    rows = [candle("BTCUSDT", minute, close_price=float(minute)) for minute in range(4)]

    fake = FakeHistoricalKlines()
    fake.seed(rows)
    store = FakeMarketDataRepository()
    store.save_klines(MarketType.SPOT, rows)
    real = StoredKlinesReader(store)

    assert fake.load("BTCUSDT", MINUTE, limit=3, newest_first=True) == real.load(
        "BTCUSDT", MINUTE, limit=3, newest_first=True
    )
