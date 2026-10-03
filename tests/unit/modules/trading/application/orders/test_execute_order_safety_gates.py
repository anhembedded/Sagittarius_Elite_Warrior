"""`ExecuteOrderCommandHandler`: the safety gates an order passes before it is sent."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client_factory import (
    FuturesTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimits,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.orders.execute_order_builders import (
    build_handler,
    make_handler,
    order_request,
    ready_status,
    static_metadata_provider,
)


class TestSafetyGates:
    def test_blocked_when_trading_venue_disabled(self) -> None:
        handler, _ = make_handler(trading_venue=TradingVenue.DISABLED)
        result = handler.execute(
            ExecuteOrderCommand(
                order_request=order_request(venue=TradingVenue.DISABLED)
            )
        )
        assert result.blocked_by is ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED
        assert result.preview is None

    def test_not_blocked_when_trading_venue_is_spot_testnet(self) -> None:
        """`EPIC-027K` — the gate asks `TradingVenue.supports_order_submission`,
        not a literal `is not FUTURES_TESTNET`, so a newly-supported venue is
        a one-property change, not a three-handler edit. `SPOT_TESTNET` now
        has a real order-submission implementation (`SpotTradingClient`,
        bound by `adapter_bindings.py`'s `ITradingClientFactory` branch), so
        `supports_order_submission` is `True` for it and this gate no longer
        blocks — see `TestLiveSubmission::test_live_submits_and_records_the_order_on_spot_testnet`
        for the full successful submission this unblocks."""
        handler, _ = make_handler(trading_venue=TradingVenue.SPOT_TESTNET)
        result = handler.execute(
            ExecuteOrderCommand(
                order_request=order_request(venue=TradingVenue.SPOT_TESTNET)
            )
        )
        assert result.blocked_by is not ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED

    def test_blocked_when_switch_is_off(self) -> None:
        handler, _ = make_handler(enabled=False)
        result = handler.execute(ExecuteOrderCommand(order_request=order_request()))
        assert result.blocked_by is ExecuteOrderSafetyGate.TRADING_SWITCH_OFF

    def test_blocked_when_another_owner_holds_the_symbols_lease(self) -> None:
        """`EPIC-025` PR 2.1f — the rule the user asked for on 2026-09-09
        (`PRO-003` §4.1.2), enforced here instead of in one screen. A manual
        order carries `OrderRequest`'s `MANUAL_OWNER` default, and the strategy
        claimed the symbol on arm."""
        handler, state = make_handler()
        state.claim_symbol("BTCUSDT", "strategy")

        result = handler.execute(ExecuteOrderCommand(order_request=order_request()))

        assert result.blocked_by is ExecuteOrderSafetyGate.SYMBOL_LEASED
        assert result.preview is None

    def test_the_lease_holder_is_not_blocked_by_its_own_lease(self) -> None:
        handler, state = make_handler()
        state.claim_symbol("BTCUSDT", "strategy")

        result = handler.execute(
            ExecuteOrderCommand(order_request=order_request(), owner_id="strategy")
        )

        assert result.blocked_by is None

    def test_a_lease_on_another_symbol_does_not_block(self) -> None:
        handler, state = make_handler()
        state.claim_symbol("ETHUSDT", "strategy")

        result = handler.execute(ExecuteOrderCommand(order_request=order_request()))

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
        metadata_provider = static_metadata_provider()
        trading_client_factory = FuturesTradingClientFactory(
            Mock(), Mock(), metadata_provider
        )
        handler = build_handler(
            venue=TradingVenue.FUTURES_TESTNET,
            state=state,
            account_reader=account_reader,
            metadata_provider=metadata_provider,
            trading_client_factory=trading_client_factory,
        )

        result = handler.execute(ExecuteOrderCommand(order_request=order_request()))

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
            return ready_status()

        account_reader.check_connection.side_effect = _claim_mid_flight
        metadata_provider = static_metadata_provider()
        trading_client_factory = FuturesTradingClientFactory(
            Mock(), Mock(), metadata_provider
        )
        handler = build_handler(
            venue=TradingVenue.FUTURES_TESTNET,
            state=state,
            account_reader=account_reader,
            metadata_provider=metadata_provider,
            trading_client_factory=trading_client_factory,
        )

        result = handler.execute(
            ExecuteOrderCommand(order_request=order_request(), live=True)
        )

        assert result.blocked_by is ExecuteOrderSafetyGate.SYMBOL_LEASED
        # The cheap gate had already passed, so evaluation reached
        # normalisation — which is how the result shape says *which* of the two
        # reads refused it.
        assert result.preview is not None

    def test_the_result_carries_the_thresholds_it_judged_against(self) -> None:
        """`EPIC-025` PR 2.1g — and it is a wiring line, so it is probed rather
        than assumed: setting `limits = None` in the handler left **920** tests
        green, which means `trade-once`'s limit table would have gone silently
        blank.

        The promise is the one `limit_context`'s own docstring makes about the
        raw numbers — what gets shown is what decided — extended to the
        thresholds on the other side of the same comparison. It is what let the
        command stop doing `container.resolve(TradingLimitPolicy)` to read one
        attribute, which was the last thing keeping it out of
        `modules/strategy`.
        """
        limits = TradingLimits(
            max_orders_per_session=7,
            max_notional_per_order=Decimal(1234),
            max_positions_per_symbol=1,
            min_order_interval=timedelta(seconds=30),
        )
        handler, _ = make_handler(limits=limits)

        result = handler.execute(ExecuteOrderCommand(order_request=order_request()))

        assert result.limits == limits
        # Paired with the context, and `None` on the same condition: a
        # safety-gate block never reaches limit evaluation, so neither field
        # can claim to describe one.
        assert result.limit_context is not None

    def test_a_safety_gate_block_carries_neither_the_numbers_nor_the_limits(
        self,
    ) -> None:
        handler, _ = make_handler(enabled=False)

        result = handler.execute(ExecuteOrderCommand(order_request=order_request()))

        assert result.blocked_by is ExecuteOrderSafetyGate.TRADING_SWITCH_OFF
        assert result.limit_context is None
        assert result.limits is None

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
        handler, _ = make_handler(status=bad_status)
        result = handler.execute(ExecuteOrderCommand(order_request=order_request()))
        assert result.blocked_by is ExecuteOrderSafetyGate.CONNECTION_NOT_READY

    def test_each_gate_blocks_independently_of_the_other_two(self) -> None:
        """`EPIC-021G` §4: each of the three safety gates must block on its
        own — turning off exactly one at a time, the other two passing."""
        # Venue off, switch on, connection ready.
        handler, _ = make_handler(trading_venue=TradingVenue.DISABLED, enabled=True)
        assert (
            handler.execute(
                ExecuteOrderCommand(
                    order_request=order_request(venue=TradingVenue.DISABLED)
                )
            ).blocked_by
            is ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED
        )

        # Venue ready, switch off, connection ready.
        handler, _ = make_handler(
            trading_venue=TradingVenue.FUTURES_TESTNET, enabled=False
        )
        assert (
            handler.execute(
                ExecuteOrderCommand(order_request=order_request())
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
        handler, _ = make_handler(enabled=True, status=bad_status)
        assert (
            handler.execute(
                ExecuteOrderCommand(order_request=order_request())
            ).blocked_by
            is ExecuteOrderSafetyGate.CONNECTION_NOT_READY
        )
