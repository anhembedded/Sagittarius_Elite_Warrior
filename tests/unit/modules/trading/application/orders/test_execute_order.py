from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.handler import (
    ExecuteOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.handler import (
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.query import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderNotionalRejection,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
    TradingLimits,
    TradingLimitViolation,
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

_CREDENTIALS = ExchangeCredentials(api_key="key", api_secret="secret")

_LIMITS = TradingLimits(
    max_orders_per_session=20,
    max_notional_per_order=Decimal(500),
    max_positions_per_symbol=1,
    min_order_interval=timedelta(seconds=60),
)


class _StaticMetadataProvider(IMarketMetadataProvider):
    def __init__(self, catalog: dict[str, FuturesSymbolMetadata]) -> None:
        self._catalog = catalog

    def get_or_fetch(self, symbol: str) -> FuturesSymbolMetadata | None:
        return self._catalog.get(symbol)

    def refresh(self) -> None:
        raise NotImplementedError


def _metadata_provider() -> IMarketMetadataProvider:
    return _StaticMetadataProvider(
        {
            "BTCUSDT": FuturesSymbolMetadata(
                symbol="BTCUSDT",
                status="TRADING",
                step_size=Decimal("0.001"),
                tick_size=Decimal("0.01"),
                min_notional=Decimal(100),
                quantity_precision=3,
                price_precision=2,
                fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
            )
        }
    )


def _ready_status() -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=10,
        usdt_balance=Decimal(1000),
        position_mode=PositionMode.ONE_WAY,
        margin_type=None,
        open_position_count=0,
    )


def _order_request(**overrides: object) -> PreviewOrderQuery:
    defaults: dict[str, object] = {
        "symbol": "BTCUSDT",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "quantity": Decimal("0.002"),
        "reference_price": Decimal(64000),
    }
    defaults.update(overrides)
    return PreviewOrderQuery(**defaults)  # type: ignore[arg-type]


def _handler(
    *,
    trading_venue: TradingVenue = TradingVenue.FUTURES_TESTNET,
    enabled: bool = True,
    status: ExchangeConnectionStatus | None = None,
    session_state: TradingSessionState | None = None,
    raw_client: Mock | None = None,
    limits: TradingLimits | None = None,
) -> tuple[ExecuteOrderCommandHandler, TradingSessionState]:
    state = session_state or TradingSessionState()
    if enabled and not state.enabled:
        state.enable(state.known_open_symbols)

    account_reader = Mock()
    account_reader.check_connection.return_value = status or _ready_status()

    session_factory = Mock()
    session_factory.create_trading_client.return_value = raw_client or Mock()
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        _CREDENTIALS, CredentialsSource.FILE
    )
    metadata_provider = _metadata_provider()
    preview_handler = PreviewOrderQueryHandler(metadata_provider)

    handler = ExecuteOrderCommandHandler(
        trading_venue,
        state,
        account_reader,
        preview_handler,
        TradingLimitPolicy(limits or _LIMITS),
        session_factory,
        credentials_provider,
        metadata_provider,
    )
    return handler, state


class TestSafetyGates:
    def test_blocked_when_trading_venue_disabled(self) -> None:
        handler, _ = _handler(trading_venue=TradingVenue.DISABLED)
        result = handler.execute(ExecuteOrderCommand(order_request=_order_request()))
        assert result.blocked_by is ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED
        assert result.preview is None

    def test_blocked_when_switch_is_off(self) -> None:
        handler, _ = _handler(enabled=False)
        result = handler.execute(ExecuteOrderCommand(order_request=_order_request()))
        assert result.blocked_by is ExecuteOrderSafetyGate.TRADING_SWITCH_OFF

    def test_blocked_when_another_owner_holds_the_symbols_lease(self) -> None:
        """`EPIC-025` PR 2.1f — the rule the user asked for on 2026-09-09
        (`PRO-003` §4.1.2), enforced here instead of in one screen. A manual
        order carries `OrderRequest`'s `MANUAL_OWNER` default, and the strategy
        claimed the symbol on arm."""
        handler, state = _handler()
        state.claim_symbol("BTCUSDT", "strategy")

        result = handler.execute(ExecuteOrderCommand(order_request=_order_request()))

        assert result.blocked_by is ExecuteOrderSafetyGate.SYMBOL_LEASED
        assert result.preview is None

    def test_the_lease_holder_is_not_blocked_by_its_own_lease(self) -> None:
        handler, state = _handler()
        state.claim_symbol("BTCUSDT", "strategy")

        result = handler.execute(
            ExecuteOrderCommand(order_request=_order_request(), owner_id="strategy")
        )

        assert result.blocked_by is None

    def test_a_lease_on_another_symbol_does_not_block(self) -> None:
        handler, state = _handler()
        state.claim_symbol("ETHUSDT", "strategy")

        result = handler.execute(ExecuteOrderCommand(order_request=_order_request()))

        assert result.blocked_by is None

    def test_the_lease_is_refused_before_any_network_call(self) -> None:
        """The refusal this replaces was explicitly free — `DashboardPresenter`
        checked before reading positions, so *"a blocked attempt costs
        nothing"*. Behind `check_connection()` the user would pay a round trip,
        and a flaky connection would report `CONNECTION_NOT_READY` about an
        order that was never going to be allowed. Proven by making the
        connection check itself fail the test if it is reached."""
        state = TradingSessionState()
        state.enable(())
        state.claim_symbol("BTCUSDT", "strategy")
        account_reader = Mock()
        account_reader.check_connection.side_effect = AssertionError(
            "the lease must be refused before the connection is read"
        )
        metadata_provider = _metadata_provider()
        handler = ExecuteOrderCommandHandler(
            TradingVenue.FUTURES_TESTNET,
            state,
            account_reader,
            PreviewOrderQueryHandler(metadata_provider),
            TradingLimitPolicy(_LIMITS),
            Mock(),
            Mock(),
            metadata_provider,
        )

        result = handler.execute(ExecuteOrderCommand(order_request=_order_request()))

        assert result.blocked_by is ExecuteOrderSafetyGate.SYMBOL_LEASED
        account_reader.check_connection.assert_not_called()

    def test_a_claim_that_lands_after_the_cheap_check_still_refuses(self) -> None:
        """The reason the lease is read **twice** — `Docs/SDD/05` §3's
        claim-then-execute.

        The cheap read ahead of `check_connection()` keeps a refusal free, but
        it is outside `live_submission_guard()`, so a strategy arming in the
        window between it and the submission would slip past. The authoritative
        read inside the guard is what closes that, and without this test it is
        a line any refactor could delete with the suite still green — checked
        by deleting it, which left all 496 tests in this module and the
        integration tier passing.

        The race is reproduced deterministically rather than with threads and a
        sleep: `check_connection()` runs *after* the cheap gate and *before*
        the guard, so claiming the symbol from inside it lands in exactly that
        window. No timing, no flake — the window is where the call is.
        """
        state = TradingSessionState()
        state.enable(())
        account_reader = Mock()

        def _claim_mid_flight() -> ExchangeConnectionStatus:
            state.claim_symbol("BTCUSDT", "strategy")
            return _ready_status()

        account_reader.check_connection.side_effect = _claim_mid_flight
        metadata_provider = _metadata_provider()
        handler = ExecuteOrderCommandHandler(
            TradingVenue.FUTURES_TESTNET,
            state,
            account_reader,
            PreviewOrderQueryHandler(metadata_provider),
            TradingLimitPolicy(_LIMITS),
            Mock(),
            Mock(),
            metadata_provider,
        )

        result = handler.execute(
            ExecuteOrderCommand(order_request=_order_request(), live=True)
        )

        assert result.blocked_by is ExecuteOrderSafetyGate.SYMBOL_LEASED
        # The cheap gate had already passed, so evaluation reached
        # normalisation — which is how the result shape says *which* of the two
        # reads refused it.
        assert result.preview is not None

    def test_blocked_when_connection_not_ready(self) -> None:
        bad_status = ExchangeConnectionStatus(
            venue=TradingVenue.FUTURES_TESTNET,
            reachable=False,
            failure=ConnectionFailureKind.NETWORK,
            server_time_skew_ms=None,
            usdt_balance=None,
            position_mode=None,
            margin_type=None,
            open_position_count=None,
        )
        handler, _ = _handler(status=bad_status)
        result = handler.execute(ExecuteOrderCommand(order_request=_order_request()))
        assert result.blocked_by is ExecuteOrderSafetyGate.CONNECTION_NOT_READY

    def test_each_gate_blocks_independently_of_the_other_two(self) -> None:
        """`EPIC-021G` §4: each of the three safety gates must block on its
        own — turning off exactly one at a time, the other two passing."""
        # Venue off, switch on, connection ready.
        handler, _ = _handler(trading_venue=TradingVenue.DISABLED, enabled=True)
        assert (
            handler.execute(
                ExecuteOrderCommand(order_request=_order_request())
            ).blocked_by
            is ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED
        )

        # Venue ready, switch off, connection ready.
        handler, _ = _handler(trading_venue=TradingVenue.FUTURES_TESTNET, enabled=False)
        assert (
            handler.execute(
                ExecuteOrderCommand(order_request=_order_request())
            ).blocked_by
            is ExecuteOrderSafetyGate.TRADING_SWITCH_OFF
        )

        # Venue ready, switch on, connection not ready.
        bad_status = ExchangeConnectionStatus(
            venue=TradingVenue.FUTURES_TESTNET,
            reachable=False,
            failure=ConnectionFailureKind.NETWORK,
            server_time_skew_ms=None,
            usdt_balance=None,
            position_mode=None,
            margin_type=None,
            open_position_count=None,
        )
        handler, _ = _handler(enabled=True, status=bad_status)
        assert (
            handler.execute(
                ExecuteOrderCommand(order_request=_order_request())
            ).blocked_by
            is ExecuteOrderSafetyGate.CONNECTION_NOT_READY
        )


class TestTradingLimits:
    def test_blocked_by_max_positions_per_symbol(self) -> None:
        """`EPIC-021G`'s own worked rejected example: an existing open
        position on the symbol blocks a second order."""
        state = TradingSessionState()
        state.enable({"BTCUSDT"})
        handler, _ = _handler(session_state=state, enabled=True)

        result = handler.execute(ExecuteOrderCommand(order_request=_order_request()))

        assert result.blocked_by is TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL
        assert result.preview is not None
        assert len(result.limit_checks) == 4

    def test_dry_run_does_not_submit_even_when_everything_passes(self) -> None:
        handler, state = _handler()

        result = handler.execute(
            ExecuteOrderCommand(order_request=_order_request(), live=False)
        )

        assert result.blocked_by is None
        assert result.submitted_order is None
        assert state.orders_sent_this_session == 0


class TestNotionalRejection:
    def test_blocked_by_min_notional_before_any_network_order_call(self) -> None:
        """`BUG-090` — `EPIC-021`'s own §1 finding 6: the rounding/notional
        policy existed since `BOT-095E1` and was never wired into the live
        order path, so an order sized under `minNotional` used to sail
        through every check here and get rejected by the exchange itself.
        BTCUSDT's `min_notional` is 100 (`_metadata_provider()`); this
        order's notional is 0.001 * 50 = 0.05."""
        raw_client = Mock()
        handler, state = _handler(raw_client=raw_client)

        result = handler.execute(
            ExecuteOrderCommand(
                order_request=_order_request(
                    quantity=Decimal("0.001"), reference_price=Decimal(50)
                ),
                live=True,
            )
        )

        assert result.blocked_by is ExecuteOrderNotionalRejection.MIN_NOTIONAL
        assert result.preview is not None
        assert result.limit_checks == ()
        assert result.submitted_order is None
        raw_client.futures_create_order.assert_not_called()
        assert state.orders_sent_this_session == 0


class TestLiveSubmission:
    def test_live_submits_and_records_the_order(self) -> None:
        raw_client = Mock()
        raw_client.futures_create_order.return_value = {}
        handler, state = _handler(raw_client=raw_client)

        result = handler.execute(
            ExecuteOrderCommand(order_request=_order_request(), live=True)
        )

        assert result.blocked_by is None
        assert result.submitted_order is not None
        raw_client.futures_create_order.assert_called_once()
        raw_client.futures_create_test_order.assert_not_called()
        assert state.orders_sent_this_session == 1
        assert state.open_position_count("BTCUSDT") == 1

    def test_unknown_symbol_raises_value_error_before_any_network_order_call(
        self,
    ) -> None:
        raw_client = Mock()
        handler, _ = _handler(raw_client=raw_client)

        with pytest.raises(ValueError, match="Unknown futures symbol"):
            handler.execute(
                ExecuteOrderCommand(
                    order_request=_order_request(symbol="UNKNOWNUSDT"), live=True
                )
            )
        raw_client.futures_create_order.assert_not_called()


class TestConcurrentDispatch:
    """`PRO-003` §8.2 / `EPIC-024B` §4.1.1 — this task adds a second real
    caller of `ExecuteOrderCommand` (a human, via the manual trading form,
    alongside the strategy's own tick). Answering "can two concurrent
    dispatches both pass a limit check that only one of them should" had
    to be settled by actually racing two threads, not by reading the code
    and reasoning about it — this is that test."""

    def test_two_concurrent_dispatches_never_exceed_the_session_order_cap(
        self,
    ) -> None:
        """`max_orders_per_session=1`: only one of two simultaneous
        dispatches may ever place a real order. A `threading.Barrier`
        lines both threads up to call `handler.execute()` as close to
        together as possible; the mock exchange call sleeps briefly so a
        pre-`EPIC-024B` build (evaluate outside any lock spanning the
        network call) has a real window to let both through."""
        tight_limits = TradingLimits(
            max_orders_per_session=1,
            max_notional_per_order=Decimal(500),
            max_positions_per_symbol=1,
            min_order_interval=timedelta(seconds=60),
        )
        raw_client = Mock()

        def _slow_create_order(**_kwargs: object) -> dict[str, object]:
            time.sleep(0.05)
            return {}

        raw_client.futures_create_order.side_effect = _slow_create_order
        handler, state = _handler(raw_client=raw_client, limits=tight_limits)

        barrier = threading.Barrier(2)
        results: list[object] = [None, None]

        def _dispatch(index: int) -> None:
            barrier.wait(timeout=5)
            results[index] = handler.execute(
                ExecuteOrderCommand(order_request=_order_request(), live=True)
            )

        threads = [
            threading.Thread(target=_dispatch, args=(0,)),
            threading.Thread(target=_dispatch, args=(1,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        assert raw_client.futures_create_order.call_count == 1
        assert state.orders_sent_this_session == 1
        blocked = [r for r in results if r.blocked_by is not None]  # type: ignore[attr-defined]
        submitted = [r for r in results if r.submitted_order is not None]  # type: ignore[attr-defined]
        assert len(submitted) == 1
        assert len(blocked) == 1
        assert blocked[0].blocked_by is TradingLimitViolation.MAX_ORDERS_PER_SESSION  # type: ignore[attr-defined]


class TestAFailedSubmissionIsNeverRecordedAsSent:
    """`SPEC-005` §5's two network rows, which were written down as promises
    before anything pinned them.

    The promise is about **ordering**, not about the error text: the handler
    records the order against the session's counters *after* the exchange call
    returns, so a submission that never landed cannot advance
    `orders_sent_this_session` or mark the symbol as believed-open. Move
    `record_order_sent()` above `place_order()` and both tests below fail —
    which is the point, because that mistake would silently consume the
    session's order budget on orders the venue never received.

    Both cases are exercised with the real exception types rather than a bare
    `Exception`: an exchange refusal reaches the caller translated
    (`OrderRejectedByExchangeError`), while a transport failure propagates
    untouched, and a test that accepts either cannot tell the two apart.
    """

    def test_an_exchange_refusal_leaves_the_session_counters_untouched(self) -> None:
        raw_client = Mock()
        raw_client.futures_create_order.side_effect = BinanceAPIException(
            None,
            400,
            json.dumps({"code": -2019, "msg": "Margin is insufficient"}),
        )
        handler, state = _handler(raw_client=raw_client)

        with pytest.raises(OrderRejectedByExchangeError) as refusal:
            handler.execute(
                ExecuteOrderCommand(order_request=_order_request(), live=True)
            )

        assert refusal.value.reason is OrderRejectionReason.INSUFFICIENT_MARGIN
        assert state.orders_sent_this_session == 0
        assert "BTCUSDT" not in state.known_open_symbols

    def test_a_transport_failure_leaves_the_session_counters_untouched(self) -> None:
        raw_client = Mock()
        raw_client.futures_create_order.side_effect = OSError("Network Dropped")
        handler, state = _handler(raw_client=raw_client)

        with pytest.raises(OSError, match="Network Dropped"):
            handler.execute(
                ExecuteOrderCommand(order_request=_order_request(), live=True)
            )

        assert state.orders_sent_this_session == 0
        assert "BTCUSDT" not in state.known_open_symbols
