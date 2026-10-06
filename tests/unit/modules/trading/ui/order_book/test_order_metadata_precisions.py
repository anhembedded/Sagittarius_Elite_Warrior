"""`OrderMetadataPrecisions` and the desk tables it feeds (`EPIC-033N`):
a price is written in its symbol's tick size and a size in its step size,
from the venue's cached order metadata; an unknown symbol keeps the
formatter's magnitude rule."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from PySide6.QtCore import QSortFilterProxyModel
from PySide6.QtWidgets import QTableView
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tabs_panel import (
    AccountTabsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_rows import (
    OrderHistoryRow,
    TradeHistoryRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_view import (
    HistoryKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    HeldTab,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    OpenOrderRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.order_metadata_precisions import (
    OrderMetadataPrecisions,
    precision_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    PositionRow,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    PRECISION_ROLE,
    Precision,
)


def _metadata(symbol: str, tick: str, step: str) -> SymbolOrderMetadata:
    return SymbolOrderMetadata(
        symbol=symbol,
        status="TRADING",
        step_size=Decimal(step),
        tick_size=Decimal(tick),
        min_notional=Decimal(5),
        quantity_precision=None,
        price_precision=None,
        fetched_at=datetime(2026, 10, 6, tzinfo=UTC),
    )


@pytest.fixture
def cache() -> InMemorySymbolOrderMetadataCache:
    filled = InMemorySymbolOrderMetadataCache()
    filled.put(_metadata("BTCUSDT", "0.10", "0.001"))
    return filled


def test_a_cached_symbol_answers_its_tick_and_step(cache):
    precisions = OrderMetadataPrecisions(cache)

    assert precisions.tick("BTCUSDT") == Precision(Decimal("0.10"))
    assert precisions.step("BTCUSDT") == Precision(Decimal("0.001"))


def test_a_symbol_not_cached_is_unknown(cache):
    precisions = OrderMetadataPrecisions(cache)

    assert precisions.tick("NEWUSDT") is None
    assert precisions.step("NEWUSDT") is None


@pytest.mark.parametrize("size", [Decimal(0), Decimal(-1), Decimal("NaN"), 0.0])
def test_a_size_that_restricts_nothing_says_nothing_of_decimals(size):
    """Binance writes "0" for a filter that does not restrict."""
    assert precision_of(size) is None


def test_a_float_size_is_read_as_the_text_it_prints():
    assert precision_of(0.01) == Precision(Decimal("0.01"))


def _position(symbol: str) -> PositionRow:
    return PositionRow(
        symbol=symbol,
        side=PositionSide.LONG,
        quantity=Decimal("0.0153"),
        entry_price=Decimal("64250.12"),
        mark_price=Decimal("64260.18"),
        unrealized_pnl=Decimal("0.15"),
        leverage=10,
        liquidation_price=Decimal("58000.07"),
    )


def _precision(model: RowTableModel, row: int, key: str) -> object:
    return model.data(model.index(row, model.column(key)), PRECISION_ROLE)


def test_the_account_tabs_quote_every_symbol_table_in_its_filters(qapp, cache):
    """The desk hands its venue's filters to the tabs once
    (`DeskPresenter`); each table of a symbol's rows answers them, and a
    column of something else (a leverage, a fee) does not."""
    panel = AccountTabsPanel(HeldTab.POSITIONS)
    panel.use_precisions(OrderMetadataPrecisions(cache))
    panel.set_positions([_position("BTCUSDT"), _position("NEWUSDT")])
    panel.set_open_orders([_open_order("BTCUSDT")])
    orders = _source(panel.history_panel(HistoryKind.ORDERS).table)
    orders.set_rows([_order_history("BTCUSDT")])
    trades = _source(panel.history_panel(HistoryKind.TRADES).table)
    trades.set_rows([_trade("BTCUSDT")])
    positions = _source(panel.positions_panel.table)
    open_orders = _source(panel.open_orders_panel.table)

    assert _precision(positions, 0, "entry") == _TICK
    assert _precision(positions, 0, "size") == _STEP
    assert _precision(positions, 0, "leverage") is None
    assert _precision(positions, 1, "entry") is None
    assert _precision(open_orders, 0, "price") == _TICK
    assert _precision(open_orders, 0, "quantity") == _STEP
    for key in ("price", "stop", "average"):
        assert _precision(orders, 0, key) == _TICK
    for key in ("quantity", "filled"):
        assert _precision(orders, 0, key) == _STEP
    assert _precision(trades, 0, "price") == _TICK
    assert _precision(trades, 0, "quantity") == _STEP
    assert _precision(trades, 0, "fee") is None


_TICK = Precision(Decimal("0.10"))
_STEP = Precision(Decimal("0.001"))


def _source(view: QTableView) -> RowTableModel:
    proxy = view.model()
    assert isinstance(proxy, QSortFilterProxyModel)
    model = proxy.sourceModel()
    assert isinstance(model, RowTableModel)
    return model


def _open_order(symbol: str) -> OpenOrderRow:
    return OpenOrderRow(
        client_order_id="c1",
        symbol=symbol,
        side=OrderSide.BUY,
        order_type="LIMIT",
        quantity=Decimal("0.0153"),
        price=Decimal("64250.12"),
        status="NEW",
        order_time=None,
    )


def _order_history(symbol: str) -> OrderHistoryRow:
    return OrderHistoryRow(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type="STOP",
        quantity=Decimal("0.0153"),
        filled=Decimal("0.01"),
        average_price=Decimal("64250.12"),
        price=Decimal("64250.12"),
        stop_price=Decimal("64000.07"),
        status="FILLED",
        created=datetime(2026, 10, 6, tzinfo=UTC),
    )


def _trade(symbol: str) -> TradeHistoryRow:
    return TradeHistoryRow(
        symbol=symbol,
        side=OrderSide.SELL,
        price=Decimal("64250.12"),
        quantity=Decimal("0.0153"),
        quote_quantity=Decimal("983.03"),
        fee=Decimal("0.00012"),
        fee_asset="BNB",
        realized_pnl=None,
        time=datetime(2026, 10, 6, tzinfo=UTC),
    )
