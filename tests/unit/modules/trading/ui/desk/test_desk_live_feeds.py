"""`EPIC-028M` — what reaches an open desk from the bus: its venue's fills
marked on the chart, its equity samples, its blocked orders and its market's
candles, and nothing of the other venue's.

@details These carry the single Trading screen's feed regressions onto the
desks when that screen left: `EPIC-021K` §2.3 (fill markers per symbol),
`EPIC-021M` (the equity chart), `BUG-084` (a blocked signal-driven order is
said on the screen), `BUG-085` (a candle at another interval never reaches the
chart) and `EPIC-028C` (another market's candle never does either). Events go
through the real bus and feeds (`desk_screen_fixtures.py`); the chart is the
desk's real `ChartCard`, observed by wrapping the one method each test reads.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from PySide6.QtWidgets import QComboBox, QLabel
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.equity_sample import (
    EquitySample,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.equity_sampled_event import (
    EquitySampledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.live_order_blocked_event import (
    LiveOrderBlockedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_chart import (
    FILL_MARKERS_KEY,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.equity_chart_adapter import (
    equity_sample_to_candle,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_fill_marker import (
    order_filled_marker,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .account_tabs_fixtures import order
from .desk_screen_fixtures import DeskWorld, build_desk, market_of
from .order_entry_fixtures import TERMS, spot_status

FUTURES = TradingVenue.FUTURES_TESTNET
SPOT = TradingVenue.SPOT_TESTNET
_AT = datetime(2026, 10, 2, 9, 30, tzinfo=UTC)


def _record(monkeypatch: pytest.MonkeyPatch, target: object, name: str) -> list[Any]:
    """Wraps `target.name` so each call is recorded, then still made."""
    calls: list[Any] = []
    original: Callable[..., Any] = getattr(target, name)

    def recorded(*args: Any) -> Any:
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(target, name, recorded)
    return calls


def _fill(
    symbol: str, venue: TradingVenue, side: OrderSide = OrderSide.BUY
) -> OrderFilledEvent:
    return OrderFilledEvent(
        order=replace(order(symbol, f"SEW-{symbol.lower()}"), side=side),
        fill_price=Decimal(59000),
        fill_quantity=Decimal("0.01"),
        venue=venue,
    )


def _candle(symbol: str, interval: str) -> MarketData:
    return MarketData(
        symbol=symbol,
        interval=interval,
        open_time=_AT,
        open_price=100.0,
        high_price=101.0,
        low_price=99.0,
        close_price=100.5,
        volume=10.0,
        close_time=_AT,
        quote_asset_volume=1000.0,
        number_of_trades=5,
        taker_buy_base_asset_volume=5.0,
        taker_buy_quote_asset_volume=500.0,
        is_closed=True,
    )


def test_a_fill_is_marked_on_its_symbols_chart_and_shown_again_with_it(
    qtbot, qapp, monkeypatch
) -> None:
    world = DeskWorld()
    desk = build_desk(qtbot, FUTURES, world)
    marked = _record(monkeypatch, desk.view.chart, "set_script_markers")
    btc, eth = _fill("BTCUSDT", FUTURES), _fill("ETHUSDT", FUTURES, OrderSide.SELL)
    assert order_filled_marker(btc) != order_filled_marker(eth)

    world.bus.emit(btc)
    world.bus.emit(eth)  # a symbol the chart is not showing
    world.bus.emit(_fill("BTCUSDT", SPOT))  # the other venue's
    qapp.processEvents()

    assert marked == [(FILL_MARKERS_KEY, [order_filled_marker(btc)])]
    desk.view.findChild(QComboBox, "cboDeskSymbol").setCurrentText("ETHUSDT")
    assert marked[-1] == (FILL_MARKERS_KEY, [order_filled_marker(eth)])


def test_each_equity_sample_of_the_venue_is_drawn(qtbot, qapp, monkeypatch) -> None:
    world = DeskWorld()
    desk = build_desk(qtbot, SPOT, world)
    drawn = _record(monkeypatch, desk.view.equity_chart, "append_closed_candle")
    spot, futures = (
        EquitySample(
            captured_at=_AT, wallet_balance=Decimal(balance), unrealized_pnl=Decimal(0)
        )
        for balance in (1000, 2000)
    )

    world.bus.emit(EquitySampledEvent(sample=spot, venue=SPOT))
    world.bus.emit(EquitySampledEvent(sample=futures, venue=FUTURES))
    qapp.processEvents()

    assert drawn == [equity_sample_to_candle(spot)]


def test_a_fill_of_the_venue_rereads_the_order_panels_balances(qtbot, qapp) -> None:
    """`EPIC-028S` (the PR 309 re-review) — the desk re-read its panel only on
    `accountChanged`, so after a strategy's fill the panel kept the balance
    from before it. The other venue's fill reads nothing."""
    world = DeskWorld()
    snapshot = FakeAccountSnapshot(spot_status())
    desk = build_desk(
        qtbot,
        SPOT,
        world,
        account_snapshot=snapshot,
        order_entry_terms=FakeOrderEntryTerms(TERMS),
    )
    panel = desk.presenter.orders
    assert panel.context.available_quote == 1000
    snapshot.answer_with(spot_status(quote_free=Decimal(900)))

    world.bus.emit(_fill("BTCUSDT", FUTURES))
    qapp.processEvents()
    assert panel.context.available_quote == 1000

    world.bus.emit(_fill("BTCUSDT", SPOT))
    qapp.processEvents()
    assert panel.context.available_quote == 900


def test_a_blocked_order_of_the_venue_is_said_on_the_desk(qtbot, qapp) -> None:
    """`BUG-084` — a strategy's order blocked by sizing or a limit was
    visible only in a log file; the desk says it."""
    world = DeskWorld()
    desk = build_desk(qtbot, FUTURES, world)

    world.bus.emit(
        LiveOrderBlockedEvent(symbol="BTCUSDT", reason="below min notional", venue=SPOT)
    )
    qapp.processEvents()
    message = desk.view.findChild(QLabel, "lblAccountTabsMessage")
    assert "below min notional" not in message.text()

    world.bus.emit(
        LiveOrderBlockedEvent(
            symbol="BTCUSDT", reason="below min notional", venue=FUTURES
        )
    )
    qapp.processEvents()
    assert message.text() == "Live order blocked (BTCUSDT): below min notional"


def test_only_its_markets_candle_at_its_interval_reaches_the_chart(
    qtbot, qapp, monkeypatch
) -> None:
    """`BUG-085`: a candle is matched by symbol *and* interval. `EPIC-028C`:
    the Spot desk streams Spot `BTCUSDT@1m` beside the Futures desk's
    Futures `BTCUSDT@1m` — same symbol, same interval, another price."""
    world = DeskWorld()
    desk = build_desk(qtbot, FUTURES, world)
    appended = _record(monkeypatch, desk.view.chart, "append_closed_candle")
    futures_market = market_of(FUTURES)

    world.bus.emit(
        MarketTickEvent(
            market_data=_candle("BTCUSDT", "5m"), market_type=futures_market
        )
    )
    world.bus.emit(
        MarketTickEvent(
            market_data=_candle("ETHUSDT", "1m"), market_type=futures_market
        )
    )
    world.bus.emit(
        MarketTickEvent(
            market_data=_candle("BTCUSDT", "1m"), market_type=MarketType.SPOT
        )
    )
    qapp.processEvents()
    assert appended == []

    world.bus.emit(
        MarketTickEvent(
            market_data=_candle("BTCUSDT", "1m"), market_type=futures_market
        )
    )
    qapp.processEvents()
    assert len(appended) == 1


def test_a_symbol_picked_after_going_live_streams_that_symbol(qtbot) -> None:
    world = DeskWorld()
    desk = build_desk(qtbot, FUTURES, world)
    desk.actions.enable_trading.trigger()

    desk.view.findChild(QComboBox, "cboDeskSymbol").setCurrentText("ETHUSDT")

    held = world.stream.held_by("desk.futures_testnet")
    assert held is not None
    assert held.symbols == ("ETHUSDT",)
    assert world.sync.was_asked_for("ETHUSDT")
