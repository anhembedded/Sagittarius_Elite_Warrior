"""`EPIC-027M` — `EmergencyStopCommandHandler`'s step 3 on a Spot venue.

Split from `test_emergency_stop.py` (`BOT-146`); the module docstring there
describes the shared testing seam.
"""

from __future__ import annotations

import json
from decimal import Decimal

from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.command import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.session.emergency_stop_builders import (
    make_handler,
    quiet_raw_client,
    spot_status,
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
        raw_client = quiet_raw_client()
        raw_client.futures_create_order.return_value = {}
        handler = make_handler(
            session_state=session_state,
            raw_client=raw_client,
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(spot_status(holdings)),
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
        raw_client = quiet_raw_client()
        handler = make_handler(
            session_state=session_state,
            raw_client=raw_client,
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(spot_status(holdings)),
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
        raw_client = quiet_raw_client()
        handler = make_handler(
            raw_client=raw_client,
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(spot_status(holdings)),
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
                # 0.0005 surplus, below the 0.001 step in `static_metadata_provider()`.
                free=Decimal("0.5005"),
                locked=Decimal(0),
                dust_threshold=Decimal("0.00000001"),
            ),
        )
        raw_client = quiet_raw_client()
        handler = make_handler(
            session_state=session_state,
            raw_client=raw_client,
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(spot_status(holdings)),
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
        raw_client = quiet_raw_client()
        handler = make_handler(
            session_state=session_state,
            raw_client=raw_client,
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(spot_status(holdings)),
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
        handler = make_handler(
            session_state=session_state,
            raw_client=quiet_raw_client(),
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(spot_status(holdings)),
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
        raw_client = quiet_raw_client()
        raw_client.futures_create_order.side_effect = BinanceAPIException(
            None, 400, json.dumps({"code": -2010, "msg": "Insufficient balance"})
        )
        handler = make_handler(
            session_state=session_state,
            raw_client=raw_client,
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(spot_status(holdings)),
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
        handler = make_handler(
            session_state=session_state,
            raw_client=quiet_raw_client(),
            trading_venue=TradingVenue.SPOT_TESTNET,
            account_reader=FakeTradingAccountReader(unreachable_status),
        )

        result = handler.execute(EmergencyStopCommand(venue=TradingVenue.SPOT_TESTNET))

        assert result.positions_closed.succeeded is False
