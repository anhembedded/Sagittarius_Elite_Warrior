"""`EPIC-039D` - registering a Futures owner's budget: the position is derived,
a position that is not the bot's is refused, a disagreement is reported.

@details The handler is real, over a real `TradingSessionState`; the venue's
history is `FakeAccountHistoryReader`, its open orders and `positionRisk` come
from a `Mock(spec=ITradingClientFactory)`, its filters from a
`Mock(spec=IMarketMetadataProvider)`, trading's own ports."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.application.session.register_owner_budget import (
    RegisterOwnerBudgetCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LiquidationPrice,
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistration,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    PositionDivergenceKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_history_reader import (
    FakeAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.owner_position_world import (
    BUDGET,
    NOW,
    REGISTRATION,
    STEP,
    TAG,
    traded,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.owner_budget_handlers import (
    registration_handler,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
    venue_context,
)

_FUTURES = TradingVenue.FUTURES_TESTNET


def _live(amount: str) -> list[LivePosition]:
    if Decimal(amount) == 0:
        return []
    return [
        LivePosition(
            "BTCUSDT",
            Decimal(amount),
            Decimal(60000),
            Decimal(60000),
            Decimal(0),
            10,
            MarginType.ISOLATED,
            LiquidationPrice(Decimal(50000)),
            NOW,
        )
    ]


def _metadata(step: Decimal | None = STEP) -> Mock:
    provider = Mock(spec=IMarketMetadataProvider)
    provider.get_or_fetch.return_value = (
        None
        if step is None
        else SymbolOrderMetadata(
            "BTCUSDT", "TRADING", step, Decimal("0.1"), Decimal(5), 3, 1, NOW
        )
    )
    return provider


def _register(
    *fills: tuple[OrderRecord, TradeRecord],
    exchange: str = "0",
    registration: OwnerBudgetRegistration = REGISTRATION,
    step: Decimal | None = STEP,
    positions_error: Exception | None = None,
    state: TradingSessionState | None = None,
) -> tuple[OwnerBudgetRegistrationResult, TradingSessionState]:
    state = state or TradingSessionState()
    state.enable(set())
    factory = Mock(spec=ITradingClientFactory)
    client = factory.create.return_value
    client.get_open_orders.return_value = []
    client.get_positions.return_value = _live(exchange)
    client.get_positions.side_effect = positions_error
    history = FakeAccountHistoryReader(
        [o for o, _ in fills], [t for _, t in fills], now=NOW
    )
    context = venue_context(
        _FUTURES,
        client_factory=factory,
        metadata_provider=_metadata(step),
        history_reader=history,  # type: ignore[arg-type]
    )
    handler = registration_handler(single_venue_scopes(context, state))
    return handler.execute(
        RegisterOwnerBudgetCommand(registration, venue=_FUTURES)
    ), state


def test_a_futures_budget_registers_with_the_position_the_fills_derive() -> None:
    result, state = _register(
        traded(1, OrderSide.BUY, "0.010", "60000"),
        traded(2, OrderSide.BUY, "0.010", "61000"),
        exchange="0.020",
    )

    assert result.registered and result.divergence is None
    assert result.inventory is None
    assert result.position is not None
    assert (result.position.quantity, result.position.average_entry) == (
        Decimal("0.020"),
        Decimal(60500),
    )
    assert state.owner_book_reads.position_of(TAG, "bot-f0") == result.position
    assert state.owner_book_reads.shares() == ()  # no Spot inventory to liquidate


def test_a_position_that_no_tagged_fill_explains_is_foreign_and_refuses() -> None:
    result, state = _register(exchange="0.050")

    assert result.refusal is OwnerBudgetRefusal.FOREIGN_POSITION
    assert result.foreign_position is not None
    assert result.foreign_position.describe() == (
        "BTCUSDT already has a long position of 0.05 that this bot did not open; "
        "close it or pick another symbol"
    )
    assert state.owner_book_reads.holder_of(TAG) is None


def test_a_short_the_user_opened_is_described_as_short() -> None:
    result, _ = _register(exchange="-0.0125")

    assert result.foreign_position is not None
    assert "short position of 0.0125" in result.foreign_position.describe()


def test_a_position_within_one_step_of_flat_is_not_foreign() -> None:
    result, _ = _register(exchange="0.001")

    assert result.registered


def test_a_bot_that_closed_everything_and_a_position_the_user_opened_after_is_foreign() -> (
    None
):
    result, _ = _register(
        traded(1, OrderSide.BUY, "0.010", "60000"),
        traded(2, OrderSide.SELL, "0.010", "61000"),
        exchange="0.050",
    )

    assert result.refusal is OwnerBudgetRefusal.FOREIGN_POSITION


def test_a_disagreement_beyond_the_owners_own_fills_registers_and_is_reported() -> None:
    result, state = _register(
        traded(1, OrderSide.BUY, "0.010", "60000"), exchange="0.050"
    )

    assert result.registered
    assert result.divergence is not None
    assert result.divergence.kind is PositionDivergenceKind.POSITION_MISMATCH
    assert (result.divergence.derived, result.divergence.exchange) == (
        Decimal("0.010"),
        Decimal("0.050"),
    )
    held = state.owner_book_reads.position_of(TAG, "bot-f0")
    assert held is not None and held.quantity == Decimal("0.010")


def test_a_forced_close_the_history_shows_without_a_tag_is_a_mismatch_not_a_fill() -> (
    None
):
    result, _ = _register(
        traded(1, OrderSide.BUY, "0.010", "60000"),
        traded(2, OrderSide.SELL, "0.010", "50000", client_order_id="autoclose-1"),
        exchange="0",
    )

    assert result.registered
    assert result.divergence is not None
    assert (result.divergence.derived, result.divergence.exchange) == (
        Decimal("0.010"),
        Decimal(0),
    )


def test_a_position_read_that_fails_refuses_the_registration() -> None:
    result, state = _register(positions_error=ConnectionError("down"))

    assert result.refusal is OwnerBudgetRefusal.INVENTORY_UNAVAILABLE
    assert state.owner_book_reads.holder_of(TAG) is None


def test_a_symbol_the_venue_does_not_list_refuses_the_registration() -> None:
    result, _ = _register(step=None)

    assert result.refusal is OwnerBudgetRefusal.INVENTORY_UNAVAILABLE


def test_a_futures_venue_refuses_a_budget_without_futures_limits() -> None:
    spot_shaped = replace(REGISTRATION, budget=replace(BUDGET, futures=None))

    result, _ = _register(registration=spot_shaped)

    assert result.refusal is OwnerBudgetRefusal.BUDGET_NOT_FOR_VENUE


def test_a_spot_venue_refuses_a_budget_with_futures_limits() -> None:
    state = TradingSessionState()
    state.enable(set())
    context = venue_context(TradingVenue.SPOT_TESTNET)
    handler = registration_handler(single_venue_scopes(context, state))

    result = handler.execute(
        RegisterOwnerBudgetCommand(REGISTRATION, venue=TradingVenue.SPOT_TESTNET)
    )

    assert result.refusal is OwnerBudgetRefusal.BUDGET_NOT_FOR_VENUE


def test_an_own_order_that_fills_between_the_two_reads_is_not_a_foreign_position() -> (
    None
):
    """The exchange is read before the history, so a fill that lands between the
    reads leaves the history ahead of it, never behind (review of PR #485)."""
    state = TradingSessionState()
    state.enable(set())
    factory = Mock(spec=ITradingClientFactory)
    client = factory.create.return_value
    client.get_open_orders.return_value = []
    client.get_positions.return_value = _live("0")

    class _FillsDuringTheHistoryRead(FakeAccountHistoryReader):
        def order_history(self, symbol: str, since: datetime):  # type: ignore[no-untyped-def]
            client.get_positions.return_value = _live("0.010")
            return super().order_history(symbol, since)

    context = venue_context(
        _FUTURES,
        client_factory=factory,
        metadata_provider=_metadata(),
        history_reader=_FillsDuringTheHistoryRead(now=NOW),  # type: ignore[arg-type]
    )
    handler = registration_handler(single_venue_scopes(context, state))

    result = handler.execute(RegisterOwnerBudgetCommand(REGISTRATION, venue=_FUTURES))

    assert result.registered
