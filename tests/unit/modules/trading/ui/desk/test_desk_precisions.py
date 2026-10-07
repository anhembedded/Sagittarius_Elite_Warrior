"""A desk writes its account tables' prices and sizes in its venue's tick
and step sizes (`EPIC-033N`): `desk_dependencies_for` reads the filters from
the venue's own metadata cache, and `DeskPresenter` hands them to the tabs."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_dependencies import (
    desk_dependencies_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    PositionRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_screen import (
    TRADE_ROUTE,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.filter_precisions import (
    FilterPrecisions,
)
from Sagittarius_Elite_Warrior.tests.conftest import fake_container
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    PRECISION_ROLE,
    Precision,
)

from .desk_screen_fixtures import build_desk

FUTURES = TradingVenue.FUTURES_TESTNET


def _cache() -> InMemorySymbolOrderMetadataCache:
    cache = InMemorySymbolOrderMetadataCache()
    cache.put(
        SymbolOrderMetadata(
            symbol="BTCUSDT",
            status="TRADING",
            step_size=Decimal("0.001"),
            tick_size=Decimal("0.10"),
            min_notional=Decimal(5),
            quantity_precision=3,
            price_precision=2,
            fetched_at=datetime(2026, 10, 6, tzinfo=UTC),
        )
    )
    return cache


def _position() -> PositionRow:
    return PositionRow(
        symbol="BTCUSDT",
        side=PositionSide.LONG,
        quantity=Decimal("0.0153"),
        entry_price=Decimal("64250.12"),
        mark_price=Decimal("64260.18"),
        unrealized_pnl=Decimal("0.15"),
        leverage=10,
        liquidation_price=None,
    )


def test_the_desk_reads_its_own_venues_filters():
    """Futures and Spot list the same symbol with different filters, so the
    desk's filters are its venue's cache, never another's."""
    cache = _cache()
    contexts = FakeVenueContexts(
        fake_venue_context(TradingVenue.SPOT_TESTNET),
        dataclasses.replace(fake_venue_context(FUTURES), metadata_cache=cache),
    )
    container = fake_container(
        {
            IVenueContexts: contexts,
            IVenueTradingPorts: FakeVenueTradingPorts(fake_venue_ports(FUTURES)),
        }
    )

    precisions = desk_dependencies_for(container, FUTURES).precisions

    assert precisions.tick("BTCUSDT") == Precision(Decimal("0.10"))
    assert precisions.step("BTCUSDT") == Precision(Decimal("0.001"))


def test_the_desk_tells_failures_through_the_containers_notifier():
    notifier = RecordingNotifier()
    container = fake_container(
        {
            IVenueContexts: FakeVenueContexts(fake_venue_context(FUTURES)),
            IVenueTradingPorts: FakeVenueTradingPorts(fake_venue_ports(FUTURES)),
            INotifier: notifier,
        }
    )

    deps = desk_dependencies_for(container, FUTURES)

    assert deps.notifier is notifier
    assert deps.chart.notifier is notifier
    assert deps.chart.scope == TRADE_ROUTE


def test_the_desk_hands_its_filters_to_the_account_tabs(qtbot):
    desk = build_desk(qtbot, FUTURES, precisions=FilterPrecisions(_cache()))

    desk.view.account_tabs.set_positions([_position()])

    proxy = desk.view.account_tabs.positions_panel.table.model()
    entry = proxy.index(0, proxy.sourceModel().column("entry"))
    assert proxy.data(entry, PRECISION_ROLE) == Precision(Decimal("0.10"))
