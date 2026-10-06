"""The Watchlist writes prices and volumes in the chosen market's tick and
step sizes (`EPIC-033N`): read from the market-data cache on every paint,
fetched on a worker once the person starts the stream, never on opening the
mode (`BUG-107`)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.symbol_market_metadata_cache import (
    InMemorySymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_market_metadata_cache import (
    ISymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_metadata_provider import (
    ISymbolMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.symbol_market_metadata import (
    LotSizeFilter,
    NotionalFilter,
    PriceFilter,
    SymbolMarketMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_dependencies import (
    MarketFilters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_metadata_precisions import (
    MarketMetadataPrecisions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_presenter import (
    MarketPresenter,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    PRECISION_ROLE,
    Precision,
)


def _metadata(symbol: str, tick: float, step: float) -> SymbolMarketMetadata:
    return SymbolMarketMetadata(
        symbol=symbol,
        status="TRADING",
        base_asset=symbol.removesuffix("USDT"),
        quote_asset="USDT",
        price_filter=PriceFilter(min_price=tick, max_price=1e6, tick_size=tick),
        lot_size_filter=LotSizeFilter(min_qty=step, max_qty=1e4, step_size=step),
        notional_filter=NotionalFilter(min_notional=5.0),
        fetched_at=datetime(2026, 10, 6, tzinfo=UTC),
    )


class _Exchange(ISymbolMetadataProvider):
    """One market's catalog, put into the shared cache on the first read, as
    the real provider fills `ISymbolMarketMetadataCache`."""

    def __init__(self, cache: ISymbolMarketMetadataCache) -> None:
        self._cache = cache
        self.reads: list[tuple[MarketType, str]] = []
        self.fails = False

    def get_or_fetch(
        self, market: MarketType, symbol: str
    ) -> SymbolMarketMetadata | None:
        self.reads.append((market, symbol))
        if self.fails:
            raise ConnectionError("exchangeInfo timed out")
        self.refresh(market)
        return self._cache.get(market, symbol)

    def refresh(self, market: MarketType) -> int:
        tick = 0.01 if market is MarketType.SPOT else 0.1
        self._cache.put(market, _metadata("BTCUSDT", tick, 0.00001))
        return 1


def test_the_precision_follows_the_chosen_market():
    cache = InMemorySymbolMarketMetadataCache()
    cache.put(MarketType.SPOT, _metadata("BTCUSDT", 0.01, 0.00001))
    cache.put(MarketType.FUTURES_USD_M, _metadata("BTCUSDT", 0.1, 0.001))
    market = [MarketType.SPOT]
    precisions = MarketMetadataPrecisions(cache, lambda: market[0])

    assert precisions.tick("BTCUSDT") == Precision(Decimal("0.01"))
    assert precisions.step("BTCUSDT") == Precision(Decimal("0.00001"))
    market[0] = MarketType.FUTURES_USD_M
    assert precisions.tick("BTCUSDT") == Precision(Decimal("0.1"))
    assert precisions.tick("ETHUSDT") is None


@pytest.fixture
def cache() -> InMemorySymbolMarketMetadataCache:
    return InMemorySymbolMarketMetadataCache()


@pytest.fixture
def exchange(cache) -> _Exchange:
    return _Exchange(cache)


@pytest.fixture
def live(build, threads, cache, exchange):
    def _live() -> MarketPresenter:
        presenter = build(filters=MarketFilters(cache, exchange))
        presenter.view.watchlist.update_tick("BTCUSDT", 64250.123, 1.5, 12.345678)
        presenter.on_mode_shown(NavigationSource.USER_INTENT)
        return presenter

    return _live


def _last_price_precision(presenter: MarketPresenter) -> object:
    model = presenter.view.watchlist
    return model.data(model.index(0, model.column("last_price")), PRECISION_ROLE)


def test_opening_the_mode_reads_no_filters(build, threads, cache, exchange):
    presenter = build(filters=MarketFilters(cache, exchange))
    presenter.on_mode_shown(NavigationSource.RESTORE)
    threads.run_all()

    assert exchange.reads == []
    assert _last_price_precision(presenter) is None


def test_going_live_reads_the_markets_filters_and_rewrites_the_rows(
    live, threads, exchange
):
    presenter = live()
    model = presenter.view.watchlist
    rewritten: list[object] = []
    model.dataChanged.connect(lambda *args: rewritten.append(args))

    threads.run_all()

    assert exchange.reads[0] == (MarketType.SPOT, "BTCUSDT")
    assert _last_price_precision(presenter) == Precision(Decimal("0.01"))
    assert rewritten


def test_a_failed_read_keeps_the_magnitude_rule(live, threads, exchange, caplog):
    exchange.fails = True
    presenter = live()

    threads.run_all()

    assert _last_price_precision(presenter) is None
    assert "could not read spot filters" in caplog.text.lower()


def test_a_read_finishing_after_the_mode_shut_down_writes_nothing(
    live, threads, exchange
):
    """Review of PR #374: the worker reported on an object the mode owned, so
    a read still running when the mode was torn down emitted on a deleted
    object. The answer is now dropped once the mode has shut down."""
    presenter = live()
    model = presenter.view.watchlist
    rewritten: list[object] = []
    model.dataChanged.connect(lambda *args: rewritten.append(args))

    presenter.shutdown()
    threads.run_all()

    assert exchange.reads == [(MarketType.SPOT, "BTCUSDT")]
    assert rewritten == []
