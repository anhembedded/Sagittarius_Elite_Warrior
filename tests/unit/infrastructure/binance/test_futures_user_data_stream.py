"""`EPIC-021H` — `FuturesUserDataStream`'s message routing:
`ORDER_TRADE_UPDATE`/`ACCOUNT_UPDATE` payloads to the right domain event
(or none), and position-state reconciliation. Uses `Mock` for the
SDK-facing boundary (`ITradingClient`, injected directly via the private
`_trading_client` attribute the real socket loop would otherwise set up
itself in `_run_stream`) and a real `MemoryEventBus`/`TradingSessionState`
— this file's job is proving the routing, not re-testing the parser
(`test_user_data_event_parser.py`) or the reconciler
(`test_position_state_reconciler.py`) it composes."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.application.services.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.domain.events.equity_sampled_event import (
    EquitySampledEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.trading.live_position import (
    LiquidationPrice,
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_user_data_stream import (
    FuturesUserDataStream,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


def _order_trade_update(**overrides: object) -> dict:
    o = {
        "s": "BTCUSDT",
        "c": "SEW-a91f4c72e0b8",
        "S": "BUY",
        "o": "MARKET",
        "f": "GTC",
        "q": "0.002",
        "p": "0",
        "sp": "0",
        "x": "TRADE",
        "X": "PARTIALLY_FILLED",
        "L": "64105.10",
        "l": "0.001",
    }
    o.update(overrides)
    return {"e": "ORDER_TRADE_UPDATE", "o": o}


def _account_update(positions: list[dict], balances: list[dict] | None = None) -> dict:
    return {
        "e": "ACCOUNT_UPDATE",
        "E": 1564745798939,
        "a": {"m": "ORDER", "B": balances or [], "P": positions},
    }


def _live_position(symbol: str = "BTCUSDT") -> LivePosition:
    return LivePosition(
        symbol=symbol,
        position_amt=Decimal("0.002"),
        entry_price=Decimal("64105.35"),
        mark_price=Decimal("64105.35"),
        unrealized_pnl=Decimal("-0.02"),
        leverage=10,
        margin_type=MarginType.CROSSED,
        liquidation_price=LiquidationPrice(Decimal(50000)),
        updated_at=datetime(2026, 8, 27, tzinfo=UTC),
    )


def _stream(
    trading_client: Mock | None = None,
    equity_recorder: EquityCurveRecorder | None = None,
) -> tuple[FuturesUserDataStream, MemoryEventBus]:
    event_bus = MemoryEventBus()
    session_state = TradingSessionState()
    stream = FuturesUserDataStream(
        event_bus,
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        session_state,
        equity_recorder if equity_recorder is not None else EquityCurveRecorder(),
    )
    # The real socket loop sets this up itself in `_run_stream`, right
    # after resolving credentials — tests exercise `_handle_message`
    # directly, so they set it up the same way here.
    stream._trading_client = trading_client
    return stream, event_bus


def test_partial_fill_publishes_order_filled_event() -> None:
    """This epic's own point: backtest never has a partial fill."""
    stream, event_bus = _stream()
    seen: list = []
    event_bus.on(OrderFilledEvent, seen.append)

    stream._handle_message(_order_trade_update(X="PARTIALLY_FILLED", x="TRADE"))

    assert len(seen) == 1
    assert seen[0].order.status.name == "PARTIALLY_FILLED"
    assert seen[0].fill_price == Decimal("64105.10")
    assert seen[0].fill_quantity == Decimal("0.001")


def test_new_acknowledgement_does_not_publish_order_filled_event() -> None:
    stream, event_bus = _stream()
    seen: list = []
    event_bus.on(OrderFilledEvent, seen.append)

    stream._handle_message(_order_trade_update(X="NEW", x="NEW"))

    assert seen == []


def test_account_update_publishes_position_changed_event() -> None:
    position = _live_position()
    trading_client = Mock()
    trading_client.get_positions.return_value = [position]
    stream, event_bus = _stream(trading_client)
    seen: list = []
    event_bus.on(PositionChangedEvent, seen.append)

    stream._handle_message(
        _account_update([{"s": "BTCUSDT", "pa": "0.002", "ep": "64105.35"}])
    )

    trading_client.get_positions.assert_called_once_with("BTCUSDT")
    assert len(seen) == 1
    assert seen[0].position is position


def test_account_update_going_flat_does_not_publish_but_still_reconciles() -> None:
    """No `LivePosition` to construct when the exchange reports flat — see
    the parser's own docstring for why this is never fabricated."""
    stream, event_bus = _stream(Mock(get_positions=Mock(return_value=[])))
    seen: list = []
    event_bus.on(PositionChangedEvent, seen.append)

    stream._handle_message(_account_update([{"s": "BTCUSDT", "pa": "0", "ep": "0"}]))

    assert seen == []
    assert stream._session_state.open_position_count("BTCUSDT") == 0


def test_account_update_before_stream_ready_does_not_crash() -> None:
    """`_trading_client` is `None` until `_run_stream` sets it up — a
    message arriving (or a misbehaving test) before that must degrade,
    not raise `AttributeError` on `None`."""
    stream, event_bus = _stream(trading_client=None)
    seen: list = []
    event_bus.on(PositionChangedEvent, seen.append)

    stream._handle_message(_account_update([{"s": "BTCUSDT", "pa": "0.002"}]))

    assert seen == []


def test_unrecognized_event_type_is_ignored() -> None:
    stream, event_bus = _stream()
    seen: list = []
    event_bus.on(OrderFilledEvent, seen.append)
    event_bus.on(PositionChangedEvent, seen.append)

    stream._handle_message({"e": "listenKeyExpired"})

    assert seen == []


def test_account_update_with_a_balance_records_and_publishes_one_equity_sample() -> (
    None
):
    """`EPIC-021M` §2.1 — recorder and event bus stay in sync: exactly one
    sample lands in both, from the same message."""
    recorder = EquityCurveRecorder()
    stream, event_bus = _stream(
        trading_client=Mock(get_positions=Mock(return_value=[])),
        equity_recorder=recorder,
    )
    seen: list = []
    event_bus.on(EquitySampledEvent, seen.append)

    stream._handle_message(
        _account_update(
            [{"s": "BTCUSDT", "pa": "0", "up": "0"}],
            balances=[{"a": "USDT", "wb": "1000.00", "cw": "1000.00"}],
        )
    )

    assert len(seen) == 1
    assert recorder.samples == [seen[0].sample]
    assert seen[0].sample.wallet_balance == Decimal("1000.00")


def test_account_update_with_no_balance_records_nothing() -> None:
    """No `'B'` entry -> no sample, not a garbage zero one (`EPIC-021M`
    §4)."""
    recorder = EquityCurveRecorder()
    stream, event_bus = _stream(
        trading_client=Mock(get_positions=Mock(return_value=[])),
        equity_recorder=recorder,
    )
    seen: list = []
    event_bus.on(EquitySampledEvent, seen.append)

    stream._handle_message(_account_update([{"s": "BTCUSDT", "pa": "0.002"}]))

    assert seen == []
    assert recorder.samples == []


async def test_run_stream_with_no_credentials_returns_without_crashing() -> None:
    """`FuturesUserDataStream` must stay safely constructible with no
    credentials configured (same reasoning as `FuturesTradingClient.
    _resolve_client()`, `EPIC-021F`) — `.start()` only fails loudly once
    the background task actually runs, never at construction/DI-resolve
    time."""
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        None, CredentialsSource.NONE
    )
    event_bus = MemoryEventBus()
    stream = FuturesUserDataStream(
        event_bus,
        Mock(),
        Mock(),
        credentials_provider,
        Mock(),
        TradingSessionState(),
        EquityCurveRecorder(),
    )
    # Would raise/hang if it tried to construct an AsyncClient with no keys.
    await stream._run_stream(CancellationToken())
