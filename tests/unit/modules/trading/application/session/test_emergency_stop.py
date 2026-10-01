"""`EPIC-021K` §2.2 — `EmergencyStopCommandHandler`.

Same testing seam `test_execute_order.py`'s `TestLiveSubmission` already
uses: the session factory is a `Mock` whose `create_trading_client`
returns a `Mock` raw `binance.client.Client` — `FuturesTradingClient`
itself runs for real (so the real mapper/params code is exercised), but
nothing reaches the network.

The 3-step ordering requirement (`EPIC-021K` §2.2: "thứ tự là một phần của
thiết kế") was mutation-verified manually while writing this file: swapping
`_disable_trading()` and the trading-client construction in
`EmergencyStopCommandHandler.execute()` made
`test_steps_run_in_the_mandated_order` fail, confirming the test actually
proves the order rather than merely exercising the code.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client_factory import (
    FuturesTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.command import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.handler import (
    EmergencyStopCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
    venue_context,
)

_CREDENTIALS = ExchangeCredentials(api_key="key", api_secret="secret")


class _StaticMetadataProvider(IMarketMetadataProvider):
    def __init__(self, catalog: dict[str, SymbolOrderMetadata]) -> None:
        self._catalog = catalog

    def get_or_fetch(self, symbol: str) -> SymbolOrderMetadata | None:
        return self._catalog.get(symbol)

    def refresh(self) -> None:
        raise NotImplementedError


def _metadata_provider() -> IMarketMetadataProvider:
    return _StaticMetadataProvider(
        {
            "BTCUSDT": SymbolOrderMetadata(
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


def _open_order_payload(
    symbol: str = "BTCUSDT", client_order_id: str = "SEW-1"
) -> dict:
    return {
        "clientOrderId": client_order_id,
        "symbol": symbol,
        "side": "BUY",
        "type": "LIMIT",
        "origQty": "0.002",
        "status": "NEW",
        "price": "63000.00",
        "stopPrice": "0",
        "reduceOnly": False,
    }


def _position_payload(symbol: str = "BTCUSDT", amt: str = "0.002") -> dict:
    # `BUG-114` — real `/fapi/v3/positionRisk` carries no `leverage`/
    # `marginType` field; `notional`/`initialMargin`/`isolatedMargin` are
    # what the mapper actually derives them from now (see
    # `futures_order_payload_mapper.py`). Values here are not meant to
    # reflect `amt` — this file never asserts leverage/margin type.
    return {
        "symbol": symbol,
        "positionAmt": amt,
        "entryPrice": "64000.00",
        "markPrice": "64500.00",
        "unRealizedProfit": "1.00",
        "notional": "128.00",
        "initialMargin": "12.80",
        "isolatedMargin": "0",
        "liquidationPrice": "0",
        "updateTime": 0,
    }


def _handler(
    *,
    session_state: TradingSessionState | Mock | None = None,
    user_data_stream: Mock | None = None,
    raw_client: Mock | None = None,
    trading_venue: TradingVenue = TradingVenue.FUTURES_TESTNET,
    account_reader: FakeTradingAccountReader | None = None,
    metadata_provider: IMarketMetadataProvider | None = None,
) -> EmergencyStopCommandHandler:
    session_factory = Mock()
    session_factory.create_trading_client.return_value = _without_algo_orders(
        raw_client or Mock()
    )
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        _CREDENTIALS, CredentialsSource.FILE
    )
    trading_client_factory = FuturesTradingClientFactory(
        session_factory, credentials_provider, _metadata_provider()
    )
    context = venue_context(
        trading_venue,
        account_reader=(
            account_reader if account_reader is not None else FakeTradingAccountReader()
        ),
        client_factory=trading_client_factory,
        metadata_provider=metadata_provider or _metadata_provider(),
        user_data_stream=user_data_stream or Mock(),
    )
    return EmergencyStopCommandHandler(
        single_venue_scopes(
            context,
            session_state if session_state is not None else TradingSessionState(),
        )
    )


def _without_algo_orders(raw_client: Mock) -> Mock:
    """`EPIC-028R` — the account holds no conditional order (Binance's Algo
    Order API) unless a test arranges one, so a test about regular orders
    keeps reading only what it arranged."""
    algo = raw_client.futures_get_open_algo_orders
    if algo.side_effect is None and not isinstance(algo.return_value, list):
        algo.return_value = []
    return raw_client


def _quiet_raw_client() -> Mock:
    """No open orders, no positions — the common case for tests that only
    care about one step."""
    raw_client = Mock()
    raw_client.futures_get_open_orders.return_value = []
    raw_client.futures_position_information.return_value = []
    return raw_client


class TestOrdering:
    def test_steps_run_in_the_mandated_order(self) -> None:
        call_order: list[str] = []

        session_state = Mock()
        session_state.disable.side_effect = lambda: call_order.append("disable_trading")
        raw_client = Mock()

        def _record_cancel(**_kwargs):
            call_order.append("cancel_orders")
            return []

        def _record_close(**_kwargs):
            call_order.append("close_positions")
            return []

        raw_client.futures_get_open_orders.side_effect = _record_cancel
        raw_client.futures_position_information.side_effect = _record_close

        handler = _handler(session_state=session_state, raw_client=raw_client)
        handler.execute(EmergencyStopCommand(venue=TradingVenue.FUTURES_TESTNET))

        # `BUG-093`'s own final-state confirmation read reuses the same
        # two raw calls (`futures_position_information`/
        # `futures_get_open_orders`, in that order — `_read_final_state`
        # calls `get_positions()` before `get_open_orders()`) one more
        # time each, after the three steps — hence the trailing repeat.
        assert call_order == [
            "disable_trading",
            "cancel_orders",
            "close_positions",
            "close_positions",
            "cancel_orders",
        ]

    def test_a_step_failing_does_not_stop_the_next_step_from_being_attempted(
        self,
    ) -> None:
        session_state = Mock()
        session_state.disable.side_effect = RuntimeError("boom")
        raw_client = _quiet_raw_client()

        handler = _handler(session_state=session_state, raw_client=raw_client)
        result = handler.execute(
            EmergencyStopCommand(venue=TradingVenue.FUTURES_TESTNET)
        )

        assert result.trading_disabled.succeeded is False
        # Called twice each: once by the step itself (2/3), once more by
        # `_read_final_state`'s own confirmation read (`BUG-093`) — step 1
        # failing must not skip either.
        assert raw_client.futures_get_open_orders.call_count == 2
        assert raw_client.futures_position_information.call_count == 2


class TestDisableTrading:
    def test_disables_the_session_and_stops_the_user_data_stream(self) -> None:
        session_state = TradingSessionState()
        session_state.enable({"BTCUSDT"})
        user_data_stream = Mock()
        handler = _handler(
            session_state=session_state,
            user_data_stream=user_data_stream,
            raw_client=_quiet_raw_client(),
        )

        result = handler.execute(
            EmergencyStopCommand(venue=TradingVenue.FUTURES_TESTNET)
        )

        assert session_state.enabled is False
        user_data_stream.stop.assert_called_once()
        assert result.trading_disabled.succeeded is True


class TestCancelAllOrders:
    def test_no_open_orders_is_a_successful_no_op(self) -> None:
        handler = _handler(raw_client=_quiet_raw_client())

        result = handler.execute(
            EmergencyStopCommand(venue=TradingVenue.FUTURES_TESTNET)
        )

        assert result.orders_cancelled.succeeded is True
        assert "No open orders" in result.orders_cancelled.detail

    def test_cancels_every_open_order_grouped_by_symbol(self) -> None:
        all_orders = [
            _open_order_payload("BTCUSDT", "SEW-1"),
            _open_order_payload("BTCUSDT", "SEW-2"),
            _open_order_payload("ETHUSDT", "SEW-3"),
        ]

        def _get_open_orders(**kwargs):
            # `FuturesTradingClient.cancel_all_orders(symbol)` re-reads
            # `get_open_orders(symbol)` internally before cancelling — see
            # that method's own docstring — so this must answer both the
            # whole-account call this handler makes and the per-symbol
            # calls made from inside each `cancel_all_orders(symbol)`.
            symbol = kwargs.get("symbol")
            if symbol is None:
                return all_orders
            return [order for order in all_orders if order["symbol"] == symbol]

        raw_client = Mock()
        raw_client.futures_get_open_orders.side_effect = _get_open_orders
        raw_client.futures_cancel_all_open_orders.return_value = {
            "code": 200,
            "msg": "ok",
        }
        raw_client.futures_position_information.return_value = []
        handler = _handler(raw_client=raw_client)

        result = handler.execute(
            EmergencyStopCommand(venue=TradingVenue.FUTURES_TESTNET)
        )

        assert result.orders_cancelled.succeeded is True
        assert "3" in result.orders_cancelled.detail
        assert raw_client.futures_cancel_all_open_orders.call_count == 2

    def test_a_rejected_cancel_reports_partial_failure_with_a_count(self) -> None:
        raw_client = Mock()
        raw_client.futures_get_open_orders.return_value = [
            _open_order_payload("BTCUSDT", "SEW-1")
        ]
        raw_client.futures_cancel_all_open_orders.side_effect = BinanceAPIException(
            None, 400, json.dumps({"code": -2011, "msg": "Unknown order"})
        )
        raw_client.futures_position_information.return_value = []
        handler = _handler(raw_client=raw_client)

        result = handler.execute(
            EmergencyStopCommand(venue=TradingVenue.FUTURES_TESTNET)
        )

        assert result.orders_cancelled.succeeded is False
        assert "0/1" in result.orders_cancelled.detail


class TestClosePositions:
    def test_no_open_positions_is_a_successful_no_op(self) -> None:
        handler = _handler(raw_client=_quiet_raw_client())

        result = handler.execute(
            EmergencyStopCommand(venue=TradingVenue.FUTURES_TESTNET)
        )

        assert result.positions_closed.succeeded is True
        assert "No open positions" in result.positions_closed.detail

    def test_closes_a_long_position_with_a_market_sell_reduce_only_order(self) -> None:
        raw_client = Mock()
        raw_client.futures_get_open_orders.return_value = []
        raw_client.futures_position_information.return_value = [
            _position_payload("BTCUSDT", amt="0.002")
        ]
        raw_client.futures_create_order.return_value = {}
        handler = _handler(raw_client=raw_client)

        result = handler.execute(
            EmergencyStopCommand(venue=TradingVenue.FUTURES_TESTNET)
        )

        assert result.positions_closed.succeeded is True
        _, kwargs = raw_client.futures_create_order.call_args
        assert kwargs["side"] == "SELL"
        assert kwargs["type"] == "MARKET"
        assert kwargs["reduceOnly"] is True
        assert kwargs["quantity"] == "0.002"

    def test_closes_a_short_position_with_a_market_buy_reduce_only_order(self) -> None:
        raw_client = Mock()
        raw_client.futures_get_open_orders.return_value = []
        raw_client.futures_position_information.return_value = [
            _position_payload("BTCUSDT", amt="-0.002")
        ]
        raw_client.futures_create_order.return_value = {}
        handler = _handler(raw_client=raw_client)

        result = handler.execute(
            EmergencyStopCommand(venue=TradingVenue.FUTURES_TESTNET)
        )

        assert result.positions_closed.succeeded is True
        _, kwargs = raw_client.futures_create_order.call_args
        assert kwargs["side"] == "BUY"

    def test_a_failure_reports_partial_failure_not_success(self) -> None:
        """`EPIC-021K`'s own worked example — the case this VO exists for:
        a step 3 failure must never render as a plain success."""
        raw_client = Mock()
        raw_client.futures_get_open_orders.return_value = []
        raw_client.futures_position_information.return_value = [
            _position_payload("BTCUSDT", amt="0.002")
        ]
        raw_client.futures_create_order.side_effect = BinanceAPIException(
            None,
            400,
            json.dumps({"code": -2019, "msg": "Margin is insufficient"}),
        )
        handler = _handler(raw_client=raw_client)

        result = handler.execute(
            EmergencyStopCommand(venue=TradingVenue.FUTURES_TESTNET)
        )

        assert result.positions_closed.succeeded is False
        assert result.fully_succeeded is False
        assert "0/1" in result.positions_closed.detail


def _spot_status(holdings: tuple[SpotHolding, ...] = ()) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.SPOT_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=10,
        usdt_balance=Decimal(1000),
        position_mode=None,
        margin_type=None,
        open_position_count=None,
        holdings=holdings,
        equity=Decimal(1000),
    )


class TestSpotClosePositions:
    """`EPIC-027M` — step 3 on a Spot venue sells each asset's surplus over
    the session's own baseline instead of closing a `LivePosition`
    (`ITradingClient.get_positions()` always answers `[]` there)."""

    def test_sells_the_surplus_over_the_baseline(self) -> None:
        session_state = TradingSessionState()
        session_state.enable(set(), spot_baseline_holdings={"BTC": Decimal("0.5")})
        holdings = (
            SpotHolding(
                asset="BTC",
                free=Decimal("0.8"),
                locked=Decimal(0),
                dust_threshold=Decimal("0.00000001"),
            ),
        )
        raw_client = _quiet_raw_client()
        raw_client.futures_create_order.return_value = {}
        handler = _handler(
            session_state=session_state,
            raw_client=raw_client,
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(_spot_status(holdings)),
        )

        result = handler.execute(EmergencyStopCommand(venue=TradingVenue.SPOT_TESTNET))

        assert result.positions_closed.succeeded is True
        _, kwargs = raw_client.futures_create_order.call_args
        assert kwargs["symbol"] == "BTCUSDT"
        assert kwargs["side"] == "SELL"
        assert kwargs["type"] == "MARKET"
        # 0.8 held - 0.5 baseline = 0.3 surplus, exactly on the 0.001 step.
        assert Decimal(kwargs["quantity"]) == Decimal("0.3")

    def test_never_sells_the_baseline_itself(self) -> None:
        """`EPIC-027M` AC3 — the worst possible failure this task exists to
        prevent: holding exactly the baseline (nothing acquired by this
        app) must place no order at all."""
        session_state = TradingSessionState()
        session_state.enable(set(), spot_baseline_holdings={"BTC": Decimal("0.5")})
        holdings = (
            SpotHolding(
                asset="BTC",
                free=Decimal("0.5"),
                locked=Decimal(0),
                dust_threshold=Decimal("0.00000001"),
            ),
        )
        raw_client = _quiet_raw_client()
        handler = _handler(
            session_state=session_state,
            raw_client=raw_client,
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(_spot_status(holdings)),
        )

        result = handler.execute(EmergencyStopCommand(venue=TradingVenue.SPOT_TESTNET))

        assert result.positions_closed.succeeded is True
        raw_client.futures_create_order.assert_not_called()

    def test_no_baseline_recorded_refuses_to_sell_anything(self) -> None:
        """`EPIC-027M` AC3's other edge: trading was never enabled on Spot
        this session (or was enabled on Futures), so there is no baseline
        at all — the safe default is to sell nothing, never to guess a
        baseline of zero and offer up the account's whole holding."""
        holdings = (
            SpotHolding(
                asset="BTC",
                free=Decimal("2.0"),
                locked=Decimal(0),
                dust_threshold=Decimal("0.00000001"),
            ),
        )
        raw_client = _quiet_raw_client()
        handler = _handler(
            raw_client=raw_client,
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(_spot_status(holdings)),
        )

        result = handler.execute(EmergencyStopCommand(venue=TradingVenue.SPOT_TESTNET))

        assert result.positions_closed.succeeded is True
        assert "No Spot holdings baseline recorded" in result.positions_closed.detail
        raw_client.futures_create_order.assert_not_called()

    def test_a_surplus_smaller_than_the_lot_step_is_reported_as_dust(self) -> None:
        session_state = TradingSessionState()
        session_state.enable(set(), spot_baseline_holdings={"BTC": Decimal("0.5")})
        holdings = (
            SpotHolding(
                asset="BTC",
                # 0.0005 surplus, below the 0.001 step in `_metadata_provider()`.
                free=Decimal("0.5005"),
                locked=Decimal(0),
                dust_threshold=Decimal("0.00000001"),
            ),
        )
        raw_client = _quiet_raw_client()
        handler = _handler(
            session_state=session_state,
            raw_client=raw_client,
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(_spot_status(holdings)),
        )

        result = handler.execute(EmergencyStopCommand(venue=TradingVenue.SPOT_TESTNET))

        assert result.positions_closed.succeeded is True
        assert "BTC" in result.positions_closed.detail
        assert "Dust" in result.positions_closed.detail
        raw_client.futures_create_order.assert_not_called()

    def test_skips_the_quote_asset(self) -> None:
        """USDT is the quote asset, never something to sell against
        itself — even a large "surplus" of it must never generate an
        order."""
        session_state = TradingSessionState()
        session_state.enable(set(), spot_baseline_holdings={})
        holdings = (
            SpotHolding(
                asset="USDT",
                free=Decimal(1000),
                locked=Decimal(0),
                dust_threshold=Decimal("0.00000001"),
            ),
        )
        raw_client = _quiet_raw_client()
        handler = _handler(
            session_state=session_state,
            raw_client=raw_client,
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(_spot_status(holdings)),
        )

        result = handler.execute(EmergencyStopCommand(venue=TradingVenue.SPOT_TESTNET))

        assert result.positions_closed.succeeded is True
        assert "No Spot holdings above the baseline" in result.positions_closed.detail
        raw_client.futures_create_order.assert_not_called()

    def test_dust_holdings_are_skipped_without_being_reported(self) -> None:
        session_state = TradingSessionState()
        session_state.enable(set(), spot_baseline_holdings={})
        holdings = (
            SpotHolding(
                asset="BTC",
                free=Decimal("0.000000005"),
                locked=Decimal(0),
                dust_threshold=Decimal("0.00000001"),
            ),
        )
        handler = _handler(
            session_state=session_state,
            raw_client=_quiet_raw_client(),
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(_spot_status(holdings)),
        )

        result = handler.execute(EmergencyStopCommand(venue=TradingVenue.SPOT_TESTNET))

        assert result.positions_closed.succeeded is True
        assert "No Spot holdings above the baseline" in result.positions_closed.detail

    def test_a_failure_selling_one_asset_reports_partial_failure(self) -> None:
        session_state = TradingSessionState()
        session_state.enable(set(), spot_baseline_holdings={"BTC": Decimal(0)})
        holdings = (
            SpotHolding(
                asset="BTC",
                free=Decimal("0.5"),
                locked=Decimal(0),
                dust_threshold=Decimal("0.00000001"),
            ),
        )
        raw_client = _quiet_raw_client()
        raw_client.futures_create_order.side_effect = BinanceAPIException(
            None, 400, json.dumps({"code": -2010, "msg": "Insufficient balance"})
        )
        handler = _handler(
            session_state=session_state,
            raw_client=raw_client,
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(_spot_status(holdings)),
        )

        result = handler.execute(EmergencyStopCommand(venue=TradingVenue.SPOT_TESTNET))

        assert result.positions_closed.succeeded is False
        assert result.fully_succeeded is False
        assert "BTC" in result.positions_closed.detail

    def test_an_unreachable_venue_reports_failure_not_a_silent_no_op(self) -> None:
        session_state = TradingSessionState()
        session_state.enable(set(), spot_baseline_holdings={"BTC": Decimal("0.5")})
        unreachable_status = ExchangeConnectionStatus(
            venue=TradingVenue.SPOT_TESTNET,
            reachable=False,
            failure=None,
            server_time_skew_ms=None,
            usdt_balance=None,
            position_mode=None,
            margin_type=None,
            open_position_count=None,
        )
        handler = _handler(
            session_state=session_state,
            raw_client=_quiet_raw_client(),
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(unreachable_status),
        )

        result = handler.execute(EmergencyStopCommand(venue=TradingVenue.SPOT_TESTNET))

        assert result.positions_closed.succeeded is False


class TestFullySucceeded:
    def test_true_only_when_all_three_steps_succeeded(self) -> None:
        handler = _handler(raw_client=_quiet_raw_client())

        result = handler.execute(
            EmergencyStopCommand(venue=TradingVenue.FUTURES_TESTNET)
        )

        assert result.fully_succeeded is True


class TestFinalState:
    """`BUG-093` — `TradingPresenter` has no other way to learn the
    account's true post-stop state: the user-data stream is already
    stopped by step 1, so nothing will emit further events for whatever
    steps 2-3 did."""

    def test_confirmed_final_state_reflects_the_post_stop_snapshot(self) -> None:
        raw_client = _quiet_raw_client()
        # `_cancel_all_orders`/`_close_all_positions` both read "empty" —
        # nothing to cancel/close — but the *final* read (after both
        # steps) reports one order and one position still present, e.g. a
        # position opened by a concurrent process the instant after this
        # command's own steps ran. `Mock(side_effect=...)` isn't needed:
        # a fixed `.return_value` already answers every call the same way,
        # so this also proves the final read is a real, separate call.
        raw_client.futures_get_open_orders.return_value = [_open_order_payload()]
        raw_client.futures_position_information.return_value = [_position_payload()]
        handler = _handler(raw_client=raw_client)

        result = handler.execute(
            EmergencyStopCommand(venue=TradingVenue.FUTURES_TESTNET)
        )

        assert result.final_state_confirmed is True
        assert len(result.final_positions) == 1
        assert result.final_positions[0].symbol == "BTCUSDT"
        assert len(result.final_open_orders) == 1
        assert result.final_open_orders[0].symbol == "BTCUSDT"

    def test_a_failed_final_read_reports_unconfirmed_not_a_false_empty(self) -> None:
        """The dangerous failure mode this guards: reporting `()` for
        `final_positions` must never be confused with "confirmed the
        account is flat" when the read itself never actually completed."""
        raw_client = _quiet_raw_client()
        # `_close_all_positions` (step 3) already called
        # `futures_position_information` once (quietly, returning `[]`) —
        # the *second* call is `_read_final_state`'s own, which is made to
        # fail here.
        raw_client.futures_position_information.side_effect = [
            [],
            RuntimeError("network lost"),
        ]
        handler = _handler(raw_client=raw_client)

        result = handler.execute(
            EmergencyStopCommand(venue=TradingVenue.FUTURES_TESTNET)
        )

        assert result.final_state_confirmed is False
        assert result.final_positions == ()
        assert result.final_open_orders == ()
        # The 3 steps' own outcomes are unaffected — this read happens
        # strictly after them and must not retroactively fail a step that
        # already succeeded.
        assert result.positions_closed.succeeded is True
