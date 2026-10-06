"""`ExecuteOrderCommandHandler`: live submission, concurrent dispatch, and a failed submission never recorded as sent."""

from __future__ import annotations

import json
import threading
import time
from datetime import timedelta
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimits,
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.orders.execute_order_builders import (
    make_handler,
    order_request,
)


class TestLiveSubmission:
    def test_live_submits_and_records_the_order(self) -> None:
        raw_client = Mock()
        raw_client.futures_create_order.return_value = {}
        handler, state = make_handler(raw_client=raw_client)

        result = handler.execute(
            ExecuteOrderCommand(order_request=order_request(), live=True)
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
        handler, _ = make_handler(raw_client=raw_client)

        with pytest.raises(ValueError, match="Unknown symbol on futures_testnet"):
            handler.execute(
                ExecuteOrderCommand(
                    order_request=order_request(symbol="UNKNOWNUSDT"), live=True
                )
            )
        raw_client.futures_create_order.assert_not_called()

    def test_live_submits_and_records_the_order_on_spot_testnet(self) -> None:
        """`EPIC-027K` — proves `SPOT_TESTNET` genuinely submits through this
        same handler once the venue's safety gate stops blocking it, not
        merely that the gate opens (`TestSafetyGates`'s own test only proves
        that)."""
        raw_client = Mock()
        raw_client.futures_create_order.return_value = {}
        handler, state = make_handler(
            trading_venue=TradingVenue.SPOT_TESTNET, raw_client=raw_client
        )

        result = handler.execute(
            ExecuteOrderCommand(
                order_request=order_request(venue=TradingVenue.SPOT_TESTNET), live=True
            )
        )

        assert result.blocked_by is None
        assert result.submitted_order is not None
        assert state.orders_sent_this_session == 1


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
        handler, state = make_handler(raw_client=raw_client, limits=tight_limits)

        barrier = threading.Barrier(2)
        results: list[object] = [None, None]

        def _dispatch(index: int) -> None:
            barrier.wait(timeout=5)
            results[index] = handler.execute(
                ExecuteOrderCommand(order_request=order_request(), live=True)
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


class TestAVenueWithoutPositionsNeverMarksASymbolOpen:
    """`BUG-142` — `max_positions_per_symbol` is a limit on *positions*, and a
    venue without positions (Spot) has none to count. The handler used to mark
    the symbol open after every manual order, nothing on Spot ever cleared it,
    and every later order on the symbol was refused until trading was enabled
    again. Real `ExecuteOrderCommandHandler`, real `TradingLimitPolicy`: a mock
    of `record_order_sent()` could not have shown this.
    """

    NO_INTERVAL = TradingLimits(
        max_orders_per_session=20,
        max_notional_per_order=Decimal(500),
        max_positions_per_symbol=1,
        min_order_interval=timedelta(0),
    )

    def _send(
        self, handler: ExecuteOrderCommandHandler, venue: TradingVenue
    ) -> ExecuteOrderResult:
        return handler.execute(
            ExecuteOrderCommand(order_request=order_request(venue=venue), live=True)
        )

    def test_a_second_order_on_the_same_spot_symbol_is_accepted(self) -> None:
        raw_client = Mock()
        raw_client.futures_create_order.return_value = {}
        handler, _ = make_handler(
            trading_venue=TradingVenue.SPOT_TESTNET,
            raw_client=raw_client,
            limits=self.NO_INTERVAL,
        )

        first = self._send(handler, TradingVenue.SPOT_TESTNET)
        second = self._send(handler, TradingVenue.SPOT_TESTNET)

        assert first.blocked_by is None
        assert second.blocked_by is None
        assert raw_client.futures_create_order.call_count == 2

    def test_a_spot_order_still_counts_against_the_session_and_the_interval(
        self,
    ) -> None:
        raw_client = Mock()
        raw_client.futures_create_order.return_value = {}
        handler, state = make_handler(
            trading_venue=TradingVenue.SPOT_TESTNET, raw_client=raw_client
        )

        self._send(handler, TradingVenue.SPOT_TESTNET)
        second = self._send(handler, TradingVenue.SPOT_TESTNET)

        assert state.orders_sent_this_session == 1
        assert "BTCUSDT" not in state.known_open_symbols
        assert second.blocked_by is TradingLimitViolation.MIN_ORDER_INTERVAL

    def test_a_second_order_on_the_same_futures_symbol_is_still_refused(self) -> None:
        raw_client = Mock()
        raw_client.futures_create_order.return_value = {}
        handler, state = make_handler(raw_client=raw_client, limits=self.NO_INTERVAL)

        first = self._send(handler, TradingVenue.FUTURES_TESTNET)
        second = self._send(handler, TradingVenue.FUTURES_TESTNET)

        assert first.blocked_by is None
        assert "BTCUSDT" in state.known_open_symbols
        assert second.blocked_by is TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL


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
        handler, state = make_handler(raw_client=raw_client)

        with pytest.raises(OrderRejectedByExchangeError) as refusal:
            handler.execute(
                ExecuteOrderCommand(order_request=order_request(), live=True)
            )

        assert refusal.value.reason is OrderRejectionReason.INSUFFICIENT_MARGIN
        assert state.orders_sent_this_session == 0
        assert "BTCUSDT" not in state.known_open_symbols

    def test_a_transport_failure_leaves_the_session_counters_untouched(self) -> None:
        raw_client = Mock()
        raw_client.futures_create_order.side_effect = OSError("Network Dropped")
        handler, state = make_handler(raw_client=raw_client)

        with pytest.raises(OSError, match="Network Dropped"):
            handler.execute(
                ExecuteOrderCommand(order_request=order_request(), live=True)
            )

        assert state.orders_sent_this_session == 0
        assert "BTCUSDT" not in state.known_open_symbols
