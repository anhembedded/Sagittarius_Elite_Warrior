"""`ExecuteOrderCommandHandler`: trading limits, and notional and stop rejections."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderNotionalRejection,
    ExecuteOrderStopRejection,
    ExecuteOrderTypeRejection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.orders.execute_order_builders import (
    make_handler,
    order_request,
)


class TestTradingLimits:
    def test_blocked_by_max_positions_per_symbol(self) -> None:
        """`EPIC-021G`'s own worked rejected example: an existing open
        position on the symbol blocks a second order."""
        state = TradingSessionState()
        state.enable({"BTCUSDT"})
        handler, _ = make_handler(session_state=state, enabled=True)

        result = handler.execute(ExecuteOrderCommand(order_request=order_request()))

        assert result.blocked_by is TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL
        assert result.preview is not None
        assert len(result.limit_checks) == 4

    def test_dry_run_does_not_submit_even_when_everything_passes(self) -> None:
        handler, state = make_handler()

        result = handler.execute(
            ExecuteOrderCommand(order_request=order_request(), live=False)
        )

        assert result.blocked_by is None
        assert result.submitted_order is None
        assert state.orders_sent_this_session == 0

    def test_the_same_four_limits_apply_unchanged_on_spot(self) -> None:
        """`EPIC-027M` AC4 — the four session limits are plain USDT/count/
        duration checks against `TradingSessionState`
        (`TradingLimitContext`), with no Futures-only assumption anywhere
        in this path; nothing about `EPIC-027M` changes them, this proves
        that stayed true rather than leaving it an unverified claim."""
        state = TradingSessionState()
        state.enable({"BTCUSDT"})
        handler, _ = make_handler(
            trading_venue=TradingVenue.SPOT_TESTNET, session_state=state, enabled=True
        )

        result = handler.execute(
            ExecuteOrderCommand(
                order_request=order_request(venue=TradingVenue.SPOT_TESTNET)
            )
        )

        assert result.blocked_by is TradingLimitViolation.MAX_POSITIONS_PER_SYMBOL
        assert len(result.limit_checks) == 4


class TestNotionalRejection:
    def test_blocked_by_min_notional_before_any_network_order_call(self) -> None:
        """`BUG-090` — `EPIC-021`'s own §1 finding 6: the rounding/notional
        policy existed since `BOT-095E1` and was never wired into the live
        order path, so an order sized under `minNotional` used to sail
        through every check here and get rejected by the exchange itself.
        BTCUSDT's `min_notional` is 100 (`static_metadata_provider()`); this
        order's notional is 0.001 * 50 = 0.05."""
        raw_client = Mock()
        handler, state = make_handler(raw_client=raw_client)

        result = handler.execute(
            ExecuteOrderCommand(
                order_request=order_request(
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


class TestStopRejection:
    @staticmethod
    def _stop_command(stop: str) -> ExecuteOrderCommand:
        return ExecuteOrderCommand(
            order_request=order_request(
                order_type=OrderType.STOP_LIMIT,
                reference_price=Decimal(64100),
                stop_price=Decimal(stop),
                last_price=Decimal(64000),
            ),
            live=True,
        )

    @pytest.mark.parametrize("stop", ["63999.99", "64000.00"], ids=["below", "at"])
    def test_a_buy_stop_not_above_the_last_price_is_never_sent(self, stop: str) -> None:
        """`EPIC-028O` — refused like `MIN_NOTIONAL`, before any request: a
        crossed stop would be rejected by Spot and triggered at once by
        Futures."""
        raw_client = Mock()
        handler, state = make_handler(raw_client=raw_client)

        result = handler.execute(self._stop_command(stop))

        assert result.blocked_by is ExecuteOrderStopRejection.STOP_ON_WRONG_SIDE
        assert result.preview is not None
        raw_client.futures_create_order.assert_not_called()
        assert state.orders_sent_this_session == 0

    @pytest.mark.parametrize("live", [False, True], ids=["dry-run", "live"])
    def test_a_type_the_venue_cannot_send_is_refused_by_name(self, live: bool) -> None:
        """A type the Futures client cannot send (`UNKNOWN`, which only a
        read produces; `STOP_MARKET` was this test's type until `EPIC-028I`
        made it sendable) is refused on the dry run and the live path alike,
        `NOT_SENDABLE_ON_VENUE`, and nothing is sent — the PR #302 review's
        should-fix 1: no clean dry run, no exception."""
        raw_client = Mock()
        handler, state = make_handler(raw_client=raw_client)

        result = handler.execute(
            ExecuteOrderCommand(
                order_request=order_request(order_type=OrderType.UNKNOWN),
                live=live,
            )
        )

        assert result.blocked_by is ExecuteOrderTypeRejection.NOT_SENDABLE_ON_VENUE
        assert result.limit_checks == ()
        raw_client.futures_create_order.assert_not_called()
        raw_client.futures_create_algo_order.assert_not_called()
        assert state.orders_sent_this_session == 0

    def test_a_futures_stop_limit_is_sent_through_the_algo_order_api(self) -> None:
        """`EPIC-028R` — one tick above the last price clears the stop gate,
        and the stop-limit is placed as a conditional order under the app's
        client order id."""
        raw_client = Mock()
        handler, state = make_handler(raw_client=raw_client)

        result = handler.execute(self._stop_command("64000.01"))

        assert result.blocked_by is None
        assert result.submitted_order is not None
        params = raw_client.futures_create_algo_order.call_args.kwargs
        assert params["clientAlgoId"] == str(result.submitted_order.client_order_id)
        assert params["triggerPrice"] == "64000.01"
        raw_client.futures_create_order.assert_not_called()
        assert state.orders_sent_this_session == 1
