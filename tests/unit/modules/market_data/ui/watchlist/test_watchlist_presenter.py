"""`WatchlistPresenter` (`BOT-019`) — seeds the tracked symbol list at
construction, starts/stops its own `IMarketStream` subscription, and updates
the table live from `MarketTickEvent` via `MarketTickFeed`."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.watchlist.watchlist_presenter import (
    WatchlistPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.watchlist.watchlist_table_model import (
    WatchlistTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.watchlist.watchlist_view import (
    WatchlistView,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_logger import ILogger


def _tick(
    symbol: str, open_price: float, close_price: float, volume: float = 100.0
) -> MarketTickEvent:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return MarketTickEvent(
        market_data=MarketData(
            symbol=symbol,
            interval="1m",
            open_time=now,
            open_price=open_price,
            high_price=max(open_price, close_price),
            low_price=min(open_price, close_price),
            close_price=close_price,
            volume=volume,
            close_time=now,
            quote_asset_volume=0.0,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.0,
            taker_buy_quote_asset_volume=0.0,
        )
    )


def _text(model: WatchlistTableModel, row: int, column: int) -> str:
    from PySide6.QtCore import Qt

    return str(model.data(model.index(row, column), Qt.ItemDataRole.DisplayRole))


@pytest.fixture
def event_bus():
    return MemoryEventBus()


@pytest.fixture
def market_stream():
    return FakeMarketStream()


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_all.return_value = {}
    config.get.side_effect = lambda key, default=None, cast=None: default
    return config


@pytest.fixture
def container(event_bus, market_stream, mock_config):
    fake = MagicMock()

    def resolve_side_effect(interface):
        if interface is IConfig:
            return mock_config
        if interface is IEventBus:
            return event_bus
        if interface is IMarketStream:
            return market_stream
        if interface is ILogger:
            return MagicMock()
        if interface is IDispatcher:
            return MagicMock()
        return MagicMock()

    fake.resolve.side_effect = resolve_side_effect
    return fake


@pytest.fixture
def view(qapp):
    return WatchlistView()


@pytest.fixture
def presenter(view, container):
    return WatchlistPresenter(view, container)


# ---------------------------------------------------------------------------
# Construction — symbols seeded, stream started
# ---------------------------------------------------------------------------


def test_construction_seeds_the_configured_symbols(view, container, mock_config):
    mock_config.get_all.return_value = {"DEFAULT_SYMBOLS": ["ETHUSDT", "SOLUSDT"]}

    WatchlistPresenter(view, container)

    assert _text(view.model, 0, WatchlistTableModel.SYMBOL_COLUMN) == "ETHUSDT"
    assert _text(view.model, 1, WatchlistTableModel.SYMBOL_COLUMN) == "SOLUSDT"


def test_construction_falls_back_to_its_own_floor_when_unconfigured(
    view, container, mock_config
):
    mock_config.get_all.return_value = {}

    WatchlistPresenter(view, container)

    assert view.model.rowCount() > 0


def test_construction_starts_the_stream_for_its_own_owner_id(presenter, market_stream):
    held = market_stream.held_by("watchlist")

    assert held is not None
    assert held.interval == TimeFrame.ONE_MINUTE


# ---------------------------------------------------------------------------
# Live ticks
# ---------------------------------------------------------------------------


def test_handle_market_tick_updates_the_row_for_its_symbol(presenter, view):
    presenter._handle_market_tick(_tick("BTCUSDT", 100.0, 105.0, 250.0))

    row = next(r for r in view.model.rows if r.symbol == "BTCUSDT")
    assert row.last_price == 105.0
    assert row.percent_change == pytest.approx(5.0)
    assert row.volume == 250.0


def test_handle_market_tick_computes_a_negative_percent_change(presenter, view):
    presenter._handle_market_tick(_tick("BTCUSDT", 100.0, 95.0))

    row = next(r for r in view.model.rows if r.symbol == "BTCUSDT")
    assert row.percent_change == pytest.approx(-5.0)


def test_handle_market_tick_with_a_zero_open_price_does_not_raise(presenter, view):
    """A malformed tick (`open_price == 0`) must not crash the slot — the
    division that would explode is guarded, not just avoided by luck."""
    presenter._handle_market_tick(_tick("BTCUSDT", 0.0, 100.0))

    row = next(r for r in view.model.rows if r.symbol == "BTCUSDT")
    assert row.last_price is None  # untouched — the tick was rejected


def test_market_tick_event_published_on_the_real_bus_reaches_the_table(
    presenter, view, event_bus
):
    """Wiring test (`testing-rule.md` §E12): publishes the real
    `MarketTickEvent` on the real bus rather than calling
    `_handle_market_tick` directly, so removing the
    `self._market_tick_feed.marketTick.connect(...)` line in
    `WatchlistPresenter.__init__` makes this fail. Mutation-verified:
    commenting out that line reproduces the failure (row stays
    untouched), restored afterwards."""
    event_bus.emit(_tick("BTCUSDT", 100.0, 110.0, 500.0))

    row = next(r for r in view.model.rows if r.symbol == "BTCUSDT")
    assert row.last_price == 110.0


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


def test_shutdown_releases_this_screens_own_stream_subscription(
    presenter, market_stream
):
    presenter.shutdown()

    assert market_stream.held_by("watchlist") is None
