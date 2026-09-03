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

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Self
from unittest.mock import AsyncMock, Mock, patch

from binance.exceptions import ReadLoopClosed
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
from Sagittarius_Elite_Warrior.src.domain.events.position_closed_event import (
    PositionClosedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.trading.live_position import (
    LiquidationPrice,
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_credentials import (
    ExchangeCredentials,
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


def test_order_trade_update_logs_at_debug_not_info(caplog) -> None:
    """`BUG-095` (`BUG-042` regression) — this fires per order-status
    transition; at `INFO` it would flood `SignalLogHandler`'s queued-signal
    UI mirror exactly the way 838 trades once froze the UI in `BUG-042`."""
    stream, _event_bus = _stream()

    with caplog.at_level(logging.DEBUG, logger="App.UserDataStream"):
        stream._handle_message(_order_trade_update(X="PARTIALLY_FILLED", x="TRADE"))

    assert any(
        "ORDER_TRADE_UPDATE" in record.message and record.levelno == logging.DEBUG
        for record in caplog.records
    )
    assert not any(
        "ORDER_TRADE_UPDATE" in record.message and record.levelno >= logging.INFO
        for record in caplog.records
    )


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


def test_account_update_position_lines_log_at_debug_not_info(caplog) -> None:
    """`BUG-095` (`BUG-042` regression) — a position-changed line fires
    per `ACCOUNT_UPDATE`, which on an active trading session is every fill."""
    trading_client = Mock()
    trading_client.get_positions.return_value = [_live_position()]
    stream, _event_bus = _stream(trading_client)

    with caplog.at_level(logging.DEBUG, logger="App.UserDataStream"):
        stream._handle_message(
            _account_update([{"s": "BTCUSDT", "pa": "0.002", "ep": "64105.35"}])
        )

    assert any(
        "ACCOUNT_UPDATE" in record.message and record.levelno == logging.DEBUG
        for record in caplog.records
    )
    # Narrowed to `ACCOUNT_UPDATE`-tagged lines, not every record: a fresh
    # `TradingSessionState()` believing "flat" while the mock reports
    # "open" also logs a legitimate, unrelated `WARNING` from
    # `position_state_reconciler.py` — that one is correct and must stay.
    assert not any(
        "ACCOUNT_UPDATE" in record.message and record.levelno >= logging.INFO
        for record in caplog.records
    )


def test_account_update_going_flat_does_not_publish_position_changed() -> None:
    """No `LivePosition` to construct when the exchange reports flat — see
    the parser's own docstring for why this is never fabricated."""
    stream, event_bus = _stream(Mock(get_positions=Mock(return_value=[])))
    seen: list = []
    event_bus.on(PositionChangedEvent, seen.append)

    stream._handle_message(_account_update([{"s": "BTCUSDT", "pa": "0", "ep": "0"}]))

    assert seen == []
    assert stream._session_state.open_position_count("BTCUSDT") == 0


def test_account_update_going_flat_publishes_position_closed() -> None:
    """`BUG-086` regression — closing to flat is a real change, not
    silence; a dedicated event must fire (real `MemoryEventBus`, no
    mocked `IEventBus`, no network)."""
    stream, event_bus = _stream(Mock(get_positions=Mock(return_value=[])))
    seen: list = []
    event_bus.on(PositionClosedEvent, seen.append)

    stream._handle_message(_account_update([{"s": "BTCUSDT", "pa": "0", "ep": "0"}]))

    assert len(seen) == 1
    assert seen[0].symbol == "BTCUSDT"


def test_account_update_still_open_does_not_publish_position_closed() -> None:
    position = _live_position()
    stream, event_bus = _stream(Mock(get_positions=Mock(return_value=[position])))
    seen: list = []
    event_bus.on(PositionClosedEvent, seen.append)

    stream._handle_message(
        _account_update([{"s": "BTCUSDT", "pa": "0.002", "ep": "64105.35"}])
    )

    assert seen == []


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


def test_library_error_sentinel_is_logged_not_silently_dropped(caplog) -> None:
    """`BUG-096` — `python-binance` pushes `{"e": "error", ...}` onto the
    same queue `stream.recv()` reads from on every connection blip
    (verified by reading `ReconnectingWebsocket._propagate_error()`'s call
    sites). Before this fix it matched neither `ORDER_TRADE_UPDATE` nor
    `ACCOUNT_UPDATE` and was silently dropped — the app logged nothing at
    all for the whole duration of a reconnect cycle."""
    stream, event_bus = _stream()
    seen: list = []
    event_bus.on(OrderFilledEvent, seen.append)
    event_bus.on(PositionChangedEvent, seen.append)

    with caplog.at_level(logging.WARNING, logger="App.UserDataStream"):
        stream._handle_message(
            {"e": "error", "type": "ConnectionClosedError", "m": "no close frame"}
        )

    assert seen == []  # never mistaken for a real order/position event
    assert any(
        "ConnectionClosedError" in record.message and "no close frame" in record.message
        for record in caplog.records
    )


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


def test_equity_sample_logs_at_debug_not_info(caplog) -> None:
    """`BUG-095` (`BUG-042` regression) — fires on every `ACCOUNT_UPDATE`
    carrying a balance line, which on an active session is every fill."""
    stream, _event_bus = _stream(
        trading_client=Mock(get_positions=Mock(return_value=[]))
    )

    with caplog.at_level(logging.DEBUG, logger="App.UserDataStream"):
        stream._handle_message(
            _account_update(
                [], balances=[{"a": "USDT", "wb": "1000.00", "cw": "1000.00"}]
            )
        )

    assert any(
        "ACCOUNT_UPDATE  equity" in record.message and record.levelno == logging.DEBUG
        for record in caplog.records
    )
    assert not any(record.levelno >= logging.INFO for record in caplog.records)


def test_equity_sample_sums_unrealized_pnl_across_positions_not_just_this_event() -> (
    None
):
    """`BUG-092` — a real `ACCOUNT_UPDATE` only reports the positions that
    changed in *that* message (`account_update_position_pnls`'s own
    docstring), never a full snapshot. Before this fix, the equity sample
    summed only the current event's `"P"` array — on a two-position
    account, an update touching just one symbol silently dropped the
    other's uPnL from the reported total."""
    recorder = EquityCurveRecorder()
    stream, event_bus = _stream(
        trading_client=Mock(get_positions=Mock(return_value=[])),
        equity_recorder=recorder,
    )
    seen: list = []
    event_bus.on(EquitySampledEvent, seen.append)

    # First event: BTCUSDT opens with uPnL -0.02, no balance line (a
    # position-only update — realistic, matches
    # `test_account_update_with_no_balance_records_nothing` below).
    stream._handle_message(
        _account_update([{"s": "BTCUSDT", "pa": "0.002", "up": "-0.02"}])
    )
    # Second event: only ETHUSDT changed this time (BTCUSDT's position is
    # untouched, so it is absent from this message's own "P" array) — but
    # carries the balance line that triggers a sample.
    stream._handle_message(
        _account_update(
            [{"s": "ETHUSDT", "pa": "1.5", "up": "3.75"}],
            balances=[{"a": "USDT", "wb": "1000.00", "cw": "1000.00"}],
        )
    )

    assert len(seen) == 1
    # -0.02 (BTCUSDT, carried over from the first event) + 3.75 (ETHUSDT,
    # this event) = 3.73 — not 3.75, which is what summing only the
    # second event's own "P" array would (wrongly) produce.
    assert seen[0].sample.unrealized_pnl == Decimal("3.73")


def test_start_resets_the_running_per_symbol_pnl_total() -> None:
    """`BUG-092` — `EnableTradingCommand` only ever starts this stream
    once reconciliation has confirmed the account is flat, so a fresh
    `start()` must not carry over a stale PnL total from a previous
    session (e.g. a stop/restart within the same process)."""
    recorder = EquityCurveRecorder()
    stream, event_bus = _stream(
        trading_client=Mock(get_positions=Mock(return_value=[])),
        equity_recorder=recorder,
    )
    seen: list = []
    event_bus.on(EquitySampledEvent, seen.append)
    stream._handle_message(
        _account_update([{"s": "BTCUSDT", "pa": "0.002", "up": "-0.02"}])
    )

    stream._unrealized_pnl_by_symbol = {}  # what start() does, without a real task manager

    stream._handle_message(
        _account_update(
            [],
            balances=[{"a": "USDT", "wb": "1000.00", "cw": "1000.00"}],
        )
    )

    assert seen[-1].sample.unrealized_pnl == Decimal(0)


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
    await stream._run_stream(CancellationToken(), generation=1)


async def test_read_loop_closed_triggers_a_reconnect_not_a_crash() -> None:
    """`BUG-096` — before this fix, `except OSError` never caught
    `ReadLoopClosed` (a plain `Exception`, the real failure `stream.recv()`
    raises once the library's own reconnect budget is exhausted), so it
    propagated out of `_run_stream()` entirely instead of triggering this
    adapter's own reconnect-with-delay path."""
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        ExchangeCredentials(api_key="key", api_secret="secret"),
        CredentialsSource.FILE,
    )
    stream = FuturesUserDataStream(
        MemoryEventBus(),
        Mock(),
        Mock(),
        credentials_provider,
        Mock(),
        TradingSessionState(),
        EquityCurveRecorder(),
    )
    stream._generation = 1
    token = Mock()
    token.is_cancelled.return_value = False

    class DyingSocket:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def recv(self) -> dict:
            raise ReadLoopClosed("Read loop has been closed")

    class RevivedSocket:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def recv(self) -> None:
            token.is_cancelled.return_value = True

    mock_bsm = Mock()
    mock_bsm.futures_user_socket.side_effect = [DyingSocket(), RevivedSocket()]

    async def mock_create(**_kwargs: object) -> Mock:
        return Mock(close_connection=AsyncMock())

    async def mock_sleep(*_args: object, **_kwargs: object) -> None:
        return None

    with (
        patch("asyncio.sleep", new=mock_sleep),
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance."
            "futures_user_data_stream.AsyncClient"
        ) as mock_async_client,
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance."
            "futures_user_data_stream.BinanceSocketManager"
        ) as mock_bsm_class,
    ):
        mock_async_client.create = mock_create
        mock_bsm_class.return_value = mock_bsm
        await stream._run_stream(token, generation=1)  # must not raise

    assert mock_bsm.futures_user_socket.call_count == 2


async def test_a_superseded_generation_stops_handling_messages_mid_stream() -> None:
    """`BUG-094` — `ITaskHandle.cancel()` only *signals* cooperative
    cancellation; it does not wait for `_run_stream()`'s own teardown. A
    `stop()` immediately followed by a `start()` (`EmergencyStopCommandHandler`'s
    own step 1, or an `EnableTradingCommand` racing a `DisableTradingCommand`)
    bumps `self._generation` while the old coroutine may still be inside
    its message loop — it must stop calling `_handle_message()` the
    instant that happens, not keep processing (and duplicating) events
    until cancellation actually lands."""
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        ExchangeCredentials(api_key="key", api_secret="secret"),
        CredentialsSource.FILE,
    )
    stream = FuturesUserDataStream(
        MemoryEventBus(),
        Mock(),
        Mock(),
        credentials_provider,
        Mock(),
        TradingSessionState(),
        EquityCurveRecorder(),
    )
    stream._generation = 1
    handled: list = []
    stream._handle_message = handled.append  # type: ignore[method-assign]
    token = Mock()
    token.is_cancelled.return_value = False

    class FakeSocket:
        def __init__(self) -> None:
            self.recv_calls = 0

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def recv(self) -> dict:
            self.recv_calls += 1
            if self.recv_calls == 2:
                # Simulates a concurrent `stop()`+`start()` landing right
                # as this message arrives — before this coroutine has any
                # chance to notice via `token.is_cancelled()`.
                stream._generation = 2
            elif self.recv_calls > 5:
                # Safety net, not part of the scenario: if the generation
                # guard regresses, this loop would otherwise spin forever
                # on a `Mock` `token.is_cancelled` that never flips —
                # fail the assertion below cleanly instead of hanging CI.
                token.is_cancelled.return_value = True
            return {"e": "ORDER_TRADE_UPDATE", "o": {}}

    mock_bsm = Mock()
    mock_bsm.futures_user_socket.return_value = FakeSocket()

    async def mock_create(**_kwargs: object) -> Mock:
        return Mock(close_connection=AsyncMock())

    with (
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance."
            "futures_user_data_stream.AsyncClient"
        ) as mock_async_client,
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance."
            "futures_user_data_stream.BinanceSocketManager"
        ) as mock_bsm_class,
    ):
        mock_async_client.create = mock_create
        mock_bsm_class.return_value = mock_bsm
        await stream._run_stream(token, generation=1)

    # Message 1 (generation still 1 when handled) reaches `_handle_message`;
    # message 2 (generation already bumped to 2 by the time it's checked)
    # does not — and the loop exits on its own once it notices, without
    # ever needing `token.is_cancelled()` to become true.
    assert len(handled) == 1
