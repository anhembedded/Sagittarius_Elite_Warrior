"""`EPIC-021G` §4 — the two acceptance checks that task listed but never
wrote: what a live `Signal` actually puts on the wire, and that a second
signal inside the blocking window never reaches the exchange at all.

@par Why these could not be unit tests
`tests/unit/application/services/test_live_trading_coordinator.py` stops at
`dispatcher.dispatch` — it proves the coordinator *asks* for the right
command, and nothing beyond. Every layer that can still lose or invert the
order's direction lives past that call: `PreviewOrderQueryHandler`'s
rounding, `map_order_to_futures_params`, and `python-binance`'s own form
encoding. §4's business-acceptance criterion is about the request Binance
receives, so the assertion has to read the request Binance received.

@par What these prove, and what they deliberately do not
The fake server (`tests/sanity/fake_exchange/`) answers regardless of
signature or timestamp, so this proves the whole chain runs end to end
(sizing -> rounding -> param mapping -> HTTP -> the exchange's own record
of the order), not Binance's signature validation. `ITradingAccountReader`
is stubbed rather than run against the fixture for one reason: the fake
account is fixed at 15,000 USDT, and this task's own 20%-of-equity sizing
would put every order past the 500 USDT notional limit, so every test here
would block on a limit before reaching the behaviour under test. The real
reader has its own round-trip coverage in
`tests/integration/infrastructure/binance/test_futures_account_reader_against_fake_server.py`.

Constructs the LIVE submission path (`ExecuteOrderCommandHandler` builds
`FuturesTradingClient(..., OrderSubmissionMode.LIVE)` itself) — the LIVE
usage guard scans only `src/`/`scripts/`, precisely so a test driving that
path against a local fixture is not mistaken for a production entry point.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.application.ports.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.application.services.live_trading_coordinator import (
    LiveTradingCoordinator,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.preview_order.handler import (
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order.handler import (
    ExecuteOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order.result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.domain.trading.policies.trading_limit_policy import (
    TradingLimitPolicy,
    TradingLimits,
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    ExchangeConnectionStatus,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.futures_symbol_metadata_cache import (
    InMemoryFuturesSymbolMetadataCache,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server

_SYMBOL = "BTCUSDT"
#: 20% of this at 1x leverage is 200 USDT of notional — comfortably inside
#: both the fixture symbol's 100 USDT `MIN_NOTIONAL` and this task's
#: 500 USDT per-order limit, so nothing here blocks on sizing by accident.
_BALANCE = Decimal(1000)
_PRICE = 64000.0

_LIMITS = TradingLimits(
    max_orders_per_session=20,
    max_notional_per_order=Decimal(500),
    max_positions_per_symbol=1,
    min_order_interval=timedelta(seconds=60),
)


class _StubAccountReader(ITradingAccountReader):
    def check_connection(self) -> ExchangeConnectionStatus:
        return ExchangeConnectionStatus(
            venue=TradingVenue.FUTURES_TESTNET,
            reachable=True,
            failure=None,
            server_time_skew_ms=10,
            usdt_balance=_BALANCE,
            position_mode=PositionMode.ONE_WAY,
            margin_type=None,
            open_position_count=0,
        )


class _FakeCredentialsProvider:
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="fake-key", api_secret="fake-secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise NotImplementedError("not used by this test")


class _RecordingDispatcher(ICommandDispatcher):
    """The real `ExecuteOrderCommandHandler` behind the port, plus a record
    of every result — the container's own resolution is a separate concern,
    covered by `tests/sanity/test_composition_root.py`."""

    def __init__(self, handler: ExecuteOrderCommandHandler) -> None:
        self._handler = handler
        self.results: list[ExecuteOrderResult] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        assert handler_class is ExecuteOrderCommand
        assert isinstance(input_dto, ExecuteOrderCommand)
        result = self._handler.execute(input_dto)
        self.results.append(result)
        return result


@dataclass
class _Pipeline:
    coordinator: LiveTradingCoordinator
    dispatcher: _RecordingDispatcher
    session_state: TradingSessionState


def _build_pipeline() -> _Pipeline:
    session_factory = ExchangeSessionFactory(MarketDataVenue.MAINNET_PUBLIC)
    metadata_provider = FuturesMetadataProvider(
        session_factory, InMemoryFuturesSymbolMetadataCache()
    )
    account_reader = _StubAccountReader()
    session_state = TradingSessionState()
    session_state.enable(set())

    handler = ExecuteOrderCommandHandler(
        TradingVenue.FUTURES_TESTNET,
        session_state,
        account_reader,
        PreviewOrderQueryHandler(metadata_provider),
        TradingLimitPolicy(_LIMITS),
        session_factory,
        _FakeCredentialsProvider(),
        metadata_provider,
    )
    dispatcher = _RecordingDispatcher(handler)
    coordinator = LiveTradingCoordinator(
        _SYMBOL,
        dispatcher,
        account_reader,
        metadata_provider,
        Mock(),
        20.0,
        1.0,
    )
    return _Pipeline(coordinator, dispatcher, session_state)


def _orders_the_exchange_received(futures_url: str) -> list[dict[str, Any]]:
    """Reads the fixture's own order book over plain HTTP rather than
    through this app's adapters — the point is what arrived on the wire,
    and asking the code under test to report that would be circular. The
    fixture records `side`/`reduceOnly`/`positionSide` straight from the
    submitted form body (`order_book_state.place()`)."""
    with urllib.request.urlopen(  # noqa: S310 — fixed localhost fixture URL
        f"{futures_url}/v1/openOrders?symbol={_SYMBOL}"
    ) as response:
        payload: list[dict[str, Any]] = json.loads(response.read().decode())
    return payload


def _signal(action: SignalAction) -> Signal:
    return Signal(
        symbol=_SYMBOL,
        action=action,
        reason="integration test",
        price=_PRICE,
        time=datetime(2026, 9, 2, tzinfo=UTC),
    )


def test_one_signal_puts_exactly_one_order_on_the_wire() -> None:
    """`EPIC-021G` §4: one `SignalGeneratedEvent` -> exactly **one** order
    sent. The count is the assertion, not a detail of it: §1 names "a
    signal loop firing hundreds of orders" as this task's real risk.

    @par What this count cannot see
    The fixture's order book is keyed by `newClientOrderId`
    (`order_book_state.py`), so submitting the *same* `Order` object twice
    collapses to one entry and reads as a pass here — verified by mutation,
    not assumed. That shape cannot occur through this pipeline
    (`PreviewOrderQueryHandler` calls `generate_client_order_id()` per
    attempt, so a re-dispatch always carries a fresh id) and real Binance
    rejects a duplicate id outright. Teaching the fixture that rejection
    would mean guessing an error code this repo has not verified from
    source, so the limitation is recorded rather than papered over. Two
    *distinct* orders reaching the wire is caught, here and in the test
    below.
    """
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        pipeline = _build_pipeline()

        pipeline.coordinator.handle(_signal(SignalAction.BUY))

        received = _orders_the_exchange_received(urls.futures)
        assert len(received) == 1
        assert received[0]["symbol"] == _SYMBOL
        assert received[0]["side"] == "BUY"
        assert pipeline.session_state.orders_sent_this_session == 1
        assert pipeline.dispatcher.results[0].blocked is False


def test_a_second_signal_inside_the_window_is_blocked_before_the_network() -> None:
    """`EPIC-021G` §4: two consecutive signals inside the blocking window ->
    the second is blocked, with a reason that can be read back.

    Asserted on the exchange's own order book, not on a return value: a
    limit that reports "blocked" while the request still went out would
    pass a mock-level test and lose real money.

    Both the position limit and the interval limit fail on that second
    attempt, and the handler reports the **first** of the four —
    `MAX_POSITIONS_PER_SYMBOL`. That is not the interval limit §4's wording
    has in mind, and it is not an accident either: `record_order_sent()`
    optimistically marks a symbol open the moment an order is sent, before
    any fill confirmation (see its own docstring). Both are asserted so a
    future change to either limit cannot silently leave the second order
    unblocked.
    """
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        pipeline = _build_pipeline()

        pipeline.coordinator.handle(_signal(SignalAction.BUY))
        pipeline.coordinator.handle(_signal(SignalAction.BUY))

        assert len(_orders_the_exchange_received(urls.futures)) == 1
        assert pipeline.session_state.orders_sent_this_session == 1

        blocked = pipeline.dispatcher.results[1]
        assert blocked.blocked is True
        assert blocked.blocked_by is TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL
        failed = {check.violation for check in blocked.limit_checks if not check.passed}
        assert failed == {
            TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL,
            TradingLimitViolation.MIN_ORDER_INTERVAL,
        }


def test_a_short_signal_opens_a_short_instead_of_closing_a_long() -> None:
    """`EPIC-021G` §4's business-acceptance check, and the one behaviour
    the whole Futures-over-Spot decision (ADR §1) exists to serve.

    In One-way mode Binance gives "open a SHORT" and "close a LONG" the
    same `side=SELL`; `reduceOnly` is the only thing separating them. Get
    it wrong and a SHORT signal silently becomes a no-op close on a flat
    account — an error that logs nothing and looks like a strategy that
    never trades.

    `test_signal_action_to_order_intent.py` locks the lookup table; this
    locks the field values Binance actually receives, three layers of
    rounding, mapping and form encoding later.
    """
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        _build_pipeline().coordinator.handle(_signal(SignalAction.SHORT))

        (received,) = _orders_the_exchange_received(urls.futures)
        assert received["side"] == "SELL"
        assert received["reduceOnly"] is False
        # One-way mode: `BOTH` is the only correct value, and sending a
        # hedge-mode `LONG`/`SHORT` here is rejected outright by Binance.
        assert received["positionSide"] == "BOTH"
        assert received["type"] == "MARKET"
        assert Decimal(received["origQty"]) > 0


def test_a_sell_signal_closes_a_long_instead_of_opening_a_short() -> None:
    """The other half of the pair above — same `side=SELL` on the wire,
    opposite `reduceOnly`. Asserting only the SHORT case would pass just as
    well against an implementation that hardcoded `reduceOnly=False`."""
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        _build_pipeline().coordinator.handle(_signal(SignalAction.SELL))

        (received,) = _orders_the_exchange_received(urls.futures)
        assert received["side"] == "SELL"
        assert received["reduceOnly"] is True
        assert received["positionSide"] == "BOTH"
