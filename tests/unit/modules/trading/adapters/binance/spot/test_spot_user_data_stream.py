"""`EPIC-027L` — `SpotUserDataStream`'s message routing: `executionReport`/
`outboundAccountPosition` payloads to the right domain event (or none), and
equity re-fetched through `ITradingAccountReader` rather than derived from
the stream's own balance deltas. Uses `FakeTradingAccountReader` (the
port's own verified fake, `testing-rule.md` §2/`architecture-rule.md`'s
"never mock a foreign port" — this one is `trading`'s own) and a real
`MemoryEventBus`/`EquityCurveRecorder` — this file's job is proving the
routing, not re-testing the parser (`test_spot_user_data_event_parser.py`)
it composes."""

from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from typing import Self
from unittest.mock import AsyncMock, Mock, patch

from binance.exceptions import ReadLoopClosed
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_user_data_stream import (
    SpotUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.equity_sampled_event import (
    EquitySampledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_ended_event import (
    OrderEndedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.emitter_builder import (
    venue_emitter,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


def _execution_report(**overrides: object) -> dict:
    payload = {
        "e": "executionReport",
        "E": 1591274595163,
        "s": "BTCUSDT",
        "c": "SEW-a91f4c72e0b8",
        "S": "BUY",
        "o": "MARKET",
        "q": "0.002",
        "x": "TRADE",
        "X": "FILLED",
        "i": 8886774,
        "l": "0.002",
        "L": "64105.10",
        "z": "0.002",
        "n": "0.0013",
        "N": "USDT",
        "T": 1591274595163,
    }
    payload.update(overrides)
    return payload


def _outbound_account_position(event_time: int = 1591274595163) -> dict:
    return {
        "e": "outboundAccountPosition",
        "E": event_time,
        "u": event_time,
        "B": [{"a": "USDT", "f": "998.00", "l": "0.00"}],
    }


def _reachable_status(equity: Decimal | None) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.SPOT_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=5,
        usdt_balance=Decimal("998.00"),
        position_mode=None,
        margin_type=None,
        open_position_count=None,
        holdings=(),
        equity=equity,
    )


def _stream(
    account_reader: FakeTradingAccountReader | None = None,
    equity_recorder: EquityCurveRecorder | None = None,
) -> tuple[SpotUserDataStream, MemoryEventBus]:
    event_bus = MemoryEventBus()
    stream = SpotUserDataStream(
        venue_emitter(event_bus, TradingVenue.SPOT_TESTNET),
        Mock(),
        Mock(),
        account_reader if account_reader is not None else FakeTradingAccountReader(),
        equity_recorder if equity_recorder is not None else EquityCurveRecorder(),
    )
    return stream, event_bus


class _SlowFakeTradingAccountReader(FakeTradingAccountReader):
    """`BOT-145` — a real blocking `time.sleep` under a real thread, not a
    mock: proves `check_connection()` runs off the event loop, which a
    `Mock`'s in-process return could not distinguish from running on it."""

    def check_connection(self) -> ExchangeConnectionStatus:
        time.sleep(0.2)
        return super().check_connection()


async def test_a_fill_publishes_order_filled_event_with_its_fee() -> None:
    stream, event_bus = _stream()
    seen: list = []
    event_bus.on(OrderFilledEvent, seen.append)

    await stream._handle_message(_execution_report())

    assert len(seen) == 1
    assert seen[0].order.status.name == "FILLED"
    assert seen[0].fill_price == Decimal("64105.10")
    assert seen[0].fill_quantity == Decimal("0.002")
    assert seen[0].fee_amount == Decimal("0.0013")
    assert seen[0].fee_asset == "USDT"
    # `EPIC-028C` — stamped with the stream's own venue.
    assert seen[0].venue is TradingVenue.SPOT_TESTNET


async def test_execution_report_logs_at_debug_not_info(caplog) -> None:
    """`BUG-095` (`BUG-042` regression), same discipline as
    `FuturesUserDataStream`'s own `ORDER_TRADE_UPDATE` line."""
    stream, _event_bus = _stream()

    with caplog.at_level(logging.DEBUG, logger="App.UserDataStream"):
        await stream._handle_message(_execution_report())

    assert any(
        "executionReport" in record.message and record.levelno == logging.DEBUG
        for record in caplog.records
    )
    assert not any(
        "executionReport" in record.message and record.levelno >= logging.INFO
        for record in caplog.records
    )


async def test_a_new_acknowledgement_does_not_publish_order_filled_event() -> None:
    stream, event_bus = _stream()
    seen: list = []
    event_bus.on(OrderFilledEvent, seen.append)

    await stream._handle_message(_execution_report(X="NEW", x="NEW", z="0", l="0"))

    assert seen == []


async def test_a_cancelled_order_publishes_order_ended_and_no_fill() -> None:
    """`EPIC-028I` — an order that ends without filling is reported, so a
    desk waiting to protect it is told — by the order's id `"C"` (`BUG-141`)."""
    stream, event_bus = _stream()
    fills: list = []
    ended: list = []
    event_bus.on(OrderFilledEvent, fills.append)
    event_bus.on(OrderEndedEvent, ended.append)
    await stream._handle_message(_execution_report())
    await stream._handle_message(
        _execution_report(X="CANCELED", x="CANCELED", c="x-cxl", C="SEW-a91f4c72e0b8")
    )
    assert [(e.order.status.name, e.order.client_order_id) for e in ended] == [
        ("CANCELED", "SEW-a91f4c72e0b8")
    ]
    assert ended[0].venue is TradingVenue.SPOT_TESTNET
    assert len(fills) == 1


async def test_a_fill_with_no_fee_fields_publishes_none_not_a_fabricated_zero() -> None:
    payload = _execution_report()
    del payload["n"]
    del payload["N"]
    stream, event_bus = _stream()
    seen: list = []
    event_bus.on(OrderFilledEvent, seen.append)

    await stream._handle_message(payload)

    assert seen[0].fee_amount is None
    assert seen[0].fee_asset is None


async def test_outbound_account_position_re_fetches_equity_and_publishes_sample() -> (
    None
):
    """`EPIC-027L` §3 — equity is re-fetched authoritatively through
    `ITradingAccountReader`, never derived from the stream's own `"B"`
    balance array (which is quote-asset-only and does not itself carry a
    priced non-quote-holding total)."""
    reader = FakeTradingAccountReader(_reachable_status(equity=Decimal("1234.56")))
    recorder = EquityCurveRecorder()
    stream, event_bus = _stream(account_reader=reader, equity_recorder=recorder)
    seen: list = []
    event_bus.on(EquitySampledEvent, seen.append)

    await stream._handle_message(_outbound_account_position())

    assert reader.checks == 1
    assert len(seen) == 1
    assert seen[0].sample.wallet_balance == Decimal("1234.56")
    assert seen[0].sample.unrealized_pnl == Decimal(0)
    assert recorder.samples() == (seen[0].sample,)


async def test_outbound_account_position_s_check_connection_does_not_stall_the_event_loop() -> (
    None
):
    """`BOT-145` — `check_connection()` is several blocking,
    `requests`-backed REST calls; before the fix they ran directly on
    `_handle_message`'s caller, the same asyncio event loop that also
    drives `stream.recv()`. Same proof shape as `FuturesUserDataStream`'s
    own `test_account_update_s_get_positions_call_does_not_stall_the_
    event_loop`: a concurrently-scheduled coroutine needing only a short
    `asyncio.sleep` must finish first."""
    order: list[str] = []
    reader = _SlowFakeTradingAccountReader(_reachable_status(equity=Decimal("1234.56")))
    stream, _event_bus = _stream(account_reader=reader)

    async def slow_task() -> None:
        await stream._handle_message(_outbound_account_position())
        order.append("slow")

    async def quick_task() -> None:
        await asyncio.sleep(0.01)
        order.append("quick")

    await asyncio.gather(slow_task(), quick_task())

    assert order == ["quick", "slow"]


class _SupersedingFakeTradingAccountReader(FakeTradingAccountReader):
    """Bumps the stream's generation mid-call — what `stop()`/`start()` do
    to a stream whose handler is suspended on the `BOT-145` REST await."""

    stream: SpotUserDataStream | None = None

    def check_connection(self) -> ExchangeConnectionStatus:
        assert self.stream is not None
        self.stream._generation += 1
        return super().check_connection()


async def test_a_generation_bumped_during_the_equity_refetch_records_nothing() -> None:
    """`BUG-094` fence, re-applied after `BOT-145`'s await: the handler passed
    the pre-dispatch generation check, then `stop()`/`start()` superseded
    the stream while `check_connection()` ran — the stale answer must not be
    recorded or published into the new session."""
    reader = _SupersedingFakeTradingAccountReader(
        _reachable_status(equity=Decimal("1234.56"))
    )
    recorder = EquityCurveRecorder()
    stream, event_bus = _stream(account_reader=reader, equity_recorder=recorder)
    reader.stream = stream
    seen: list = []
    event_bus.on(EquitySampledEvent, seen.append)

    await stream._handle_message(_outbound_account_position())

    assert reader.checks == 1
    assert seen == []
    assert recorder.samples() == ()


async def test_outbound_account_position_logs_at_debug_not_info(caplog) -> None:
    reader = FakeTradingAccountReader(_reachable_status(equity=Decimal("1234.56")))
    stream, _event_bus = _stream(account_reader=reader)

    with caplog.at_level(logging.DEBUG, logger="App.UserDataStream"):
        await stream._handle_message(_outbound_account_position())

    assert any(
        "outboundAccountPosition" in record.message and record.levelno == logging.DEBUG
        for record in caplog.records
    )
    assert not any(record.levelno >= logging.INFO for record in caplog.records)


async def test_balance_update_also_re_fetches_equity_and_publishes_sample() -> None:
    """`EPIC-027L` acceptance criteria's own "balances from
    outboundAccountPosition/balanceUpdate" — a deposit/withdrawal/dust
    conversion never produces a fill (no `executionReport`/
    `outboundAccountPosition` pair), so `balanceUpdate` must trigger the
    same authoritative equity re-fetch on its own."""
    reader = FakeTradingAccountReader(_reachable_status(equity=Decimal("2000.00")))
    recorder = EquityCurveRecorder()
    stream, event_bus = _stream(account_reader=reader, equity_recorder=recorder)
    seen: list = []
    event_bus.on(EquitySampledEvent, seen.append)

    await stream._handle_message(
        {"e": "balanceUpdate", "E": 1573200697110, "a": "BTC", "d": "1.00000000"}
    )

    assert reader.checks == 1
    assert len(seen) == 1
    assert seen[0].sample.wallet_balance == Decimal("2000.00")


async def test_outbound_account_position_with_unavailable_equity_records_nothing() -> (
    None
):
    """`SpotAccountReader._compute_equity` reports `None`, never a partial
    sum, when a holding cannot be priced — this stream must not fabricate a
    sample from an incomplete answer."""
    reader = FakeTradingAccountReader(_reachable_status(equity=None))
    recorder = EquityCurveRecorder()
    stream, event_bus = _stream(account_reader=reader, equity_recorder=recorder)
    seen: list = []
    event_bus.on(EquitySampledEvent, seen.append)

    await stream._handle_message(_outbound_account_position())

    assert seen == []
    assert recorder.samples() == ()


async def test_outbound_account_position_with_unreachable_venue_records_nothing() -> (
    None
):
    reader = FakeTradingAccountReader(
        ExchangeConnectionStatus(
            venue=TradingVenue.SPOT_TESTNET,
            reachable=False,
            failure=ConnectionFailureKind.NETWORK,
            server_time_skew_ms=None,
            usdt_balance=None,
            position_mode=None,
            margin_type=None,
            open_position_count=None,
        )
    )
    stream, event_bus = _stream(account_reader=reader)
    seen: list = []
    event_bus.on(EquitySampledEvent, seen.append)

    await stream._handle_message(_outbound_account_position())

    assert seen == []


async def test_unrecognized_event_type_is_ignored() -> None:
    stream, event_bus = _stream()
    seen: list = []
    event_bus.on(OrderFilledEvent, seen.append)
    event_bus.on(EquitySampledEvent, seen.append)

    await stream._handle_message({"e": "listenKeyExpired"})

    assert seen == []


async def test_library_error_sentinel_is_logged_not_silently_dropped(caplog) -> None:
    """`BUG-096`'s same reconnect-sentinel handling as `FuturesUserDataStream`."""
    stream, event_bus = _stream()
    seen: list = []
    event_bus.on(OrderFilledEvent, seen.append)
    event_bus.on(EquitySampledEvent, seen.append)

    with caplog.at_level(logging.WARNING, logger="App.UserDataStream"):
        await stream._handle_message(
            {"e": "error", "type": "ConnectionClosedError", "m": "no close frame"}
        )

    assert seen == []
    assert any(
        "ConnectionClosedError" in record.message and "no close frame" in record.message
        for record in caplog.records
    )


async def test_run_stream_with_no_credentials_returns_without_crashing() -> None:
    """Same reasoning as `FuturesUserDataStream`'s own test: this class must
    stay safely constructible with no credentials configured, and only fail
    loudly once the background task actually runs."""
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        None, CredentialsSource.NONE
    )
    stream = SpotUserDataStream(
        venue_emitter(MemoryEventBus(), TradingVenue.SPOT_TESTNET),
        Mock(),
        credentials_provider,
        FakeTradingAccountReader(),
        EquityCurveRecorder(),
    )
    # Would raise/hang if it tried to construct an AsyncClient with no keys.
    await stream._run_stream(CancellationToken(), generation=1)


async def test_read_loop_closed_triggers_a_reconnect_not_a_crash() -> None:
    """`BUG-096`'s same regression, ported to the Spot socket entry point
    (`bsm.user_socket()` instead of `bsm.futures_user_socket()`)."""
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        ExchangeCredentials(api_key="key", api_secret="secret"),
        CredentialsSource.FILE,
    )
    stream = SpotUserDataStream(
        venue_emitter(MemoryEventBus(), TradingVenue.SPOT_TESTNET),
        Mock(),
        credentials_provider,
        FakeTradingAccountReader(),
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
    mock_bsm.user_socket.side_effect = [DyingSocket(), RevivedSocket()]

    async def mock_create(**_kwargs: object) -> Mock:
        return Mock(close_connection=AsyncMock())

    async def mock_sleep(*_args: object, **_kwargs: object) -> None:
        return None

    with (
        patch("asyncio.sleep", new=mock_sleep),
        patch(
            "Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance."
            "spot.spot_user_data_stream.AsyncClient"
        ) as mock_async_client,
        patch(
            "Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance."
            "spot.spot_user_data_stream.BinanceSocketManager"
        ) as mock_bsm_class,
    ):
        mock_async_client.create = mock_create
        mock_bsm_class.return_value = mock_bsm
        await stream._run_stream(token, generation=1)  # must not raise

    assert mock_bsm.user_socket.call_count == 2


async def test_a_superseded_generation_stops_handling_messages_mid_stream() -> None:
    """`BUG-094`'s same fencing as `FuturesUserDataStream`'s own test."""
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        ExchangeCredentials(api_key="key", api_secret="secret"),
        CredentialsSource.FILE,
    )
    stream = SpotUserDataStream(
        venue_emitter(MemoryEventBus(), TradingVenue.SPOT_TESTNET),
        Mock(),
        credentials_provider,
        FakeTradingAccountReader(),
        EquityCurveRecorder(),
    )
    stream._generation = 1
    handled: list = []

    async def _record(payload: dict) -> None:
        handled.append(payload)

    stream._handle_message = _record  # type: ignore[method-assign]
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
                stream._generation = 2
            elif self.recv_calls > 5:
                token.is_cancelled.return_value = True
            return {"e": "executionReport"}

    mock_bsm = Mock()
    mock_bsm.user_socket.return_value = FakeSocket()

    async def mock_create(**_kwargs: object) -> Mock:
        return Mock(close_connection=AsyncMock())

    with (
        patch(
            "Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance."
            "spot.spot_user_data_stream.AsyncClient"
        ) as mock_async_client,
        patch(
            "Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance."
            "spot.spot_user_data_stream.BinanceSocketManager"
        ) as mock_bsm_class,
    ):
        mock_async_client.create = mock_create
        mock_bsm_class.return_value = mock_bsm
        await stream._run_stream(token, generation=1)

    assert len(handled) == 1
