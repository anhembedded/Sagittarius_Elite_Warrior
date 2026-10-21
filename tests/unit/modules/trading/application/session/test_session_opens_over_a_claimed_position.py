"""`BUG-250` - a closed order session opens over a position a claim's history explains, and says why
it will not over any other.

@details `SessionReadiness` over the real explainer: the venue's positions come from a
`Mock(spec=ITradingClientFactory)`, its history from `FakeAccountHistoryReader`. With no claim every
position refuses, as before; with a claim whose tagged history adds up to the position the session
opens and marks the symbol open; a position beyond it refuses with the symbol and both figures in
the refusal's own words.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.application.session.session_readiness import (
    SessionReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
    MarginType,
    PositionMode,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position_claim import (
    OwnerPositionClaim,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_block_words import (
    refusal_words,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionBlockReason,
    SessionReadyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_history_reader import (
    FakeAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.owner_position_world import (
    NOW,
    RUN,
    STEP,
    TAG,
    traded,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.recording_publisher import (
    RecordingPublisher,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    position_explainer,
    single_venue_scopes,
    venue_context,
)

_FUTURES = TradingVenue.FUTURES_TESTNET
_CLAIM = OwnerPositionClaim("bot-f0", TAG, "BTCUSDT", RUN)


def _open(
    held: str, claims: tuple[OwnerPositionClaim, ...]
) -> tuple[SessionReadyResult, TradingSessionState]:
    state = TradingSessionState()
    reader = Mock()
    reader.check_connection.return_value = ExchangeConnectionStatus(
        venue=_FUTURES,
        reachable=True,
        failure=None,
        server_time_skew_ms=10,
        usdt_balance=Decimal(1000),
        position_mode=PositionMode.ONE_WAY,
        margin_type=None,
        open_position_count=1,
    )
    factory = Mock(spec=ITradingClientFactory)
    client = factory.create.return_value
    client.get_open_orders.return_value = []
    client.get_positions.return_value = [
        LivePosition(
            "BTCUSDT",
            Decimal(held),
            Decimal(60000),
            Decimal(60000),
            Decimal(0),
            10,
            MarginType.ISOLATED,
            LiquidationPrice(Decimal(50000)),
            NOW,
        )
    ]
    metadata = Mock(spec=IMarketMetadataProvider)
    metadata.get_or_fetch.return_value = SymbolOrderMetadata(
        "BTCUSDT", "TRADING", STEP, Decimal("0.1"), Decimal(5), 3, 1, NOW
    )
    record, trade = traded(1, OrderSide.BUY, "0.010", "60000")
    history = FakeAccountHistoryReader([record], [trade], now=NOW)
    readiness = SessionReadiness(
        single_venue_scopes(
            venue_context(
                _FUTURES,
                account_reader=reader,
                client_factory=factory,
                metadata_provider=metadata,
                history_reader=history,  # type: ignore[arg-type]
                user_data_stream=Mock(),
            ),
            state,
        ),
        RecordingPublisher(),
        position_explainer(),
    )
    return readiness.ensure_ready(_FUTURES, "bot-f0", claims), state


def test_without_a_claim_every_position_refuses_as_before() -> None:
    result, state = _open("0.010", ())

    assert result.block_reason is SessionBlockReason.UNEXPECTED_POSITIONS
    assert state.enabled is False
    assert result.account_was_read is True
    assert len(result.reconciled_positions) == 1


def test_a_claim_whose_history_explains_the_position_opens_the_session() -> None:
    result, state = _open("0.010", (_CLAIM,))

    assert result.ready is True and result.unexplained_positions == ()
    assert state.enabled is True
    assert state.known_open_symbols == {"BTCUSDT"}, (
        "the symbol is open, as the stream finds it"
    )


def test_a_position_beyond_the_claims_history_refuses_with_its_figures() -> None:
    result, state = _open("0.510", (_CLAIM,))

    assert result.block_reason is SessionBlockReason.UNEXPECTED_POSITIONS
    assert state.enabled is False
    words = refusal_words(result)
    assert words.startswith("The account has unexpected open positions")
    assert "BTCUSDT holds 0.510" in words and "account for 0.010" in words
