"""`BUG-250` - which positions of the account a closed order session may open over.

@details `PositionExplainer` over the real deriver and `FakeAccountHistoryReader`, the venue's
client and filters as `test_register_owner_budget_futures.py` arranges them. A position is excused
only by the tagged history of a claim on its symbol, within one quantity step; everything else is
named with its figures. Mutation-verified: dropping the tolerance comparison, the claim lookup or
the unverifiable branch turns the matching test red.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.application.session.position_explainer import (
    PositionExplainer,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LiquidationPrice,
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position_claim import (
    OwnerPositionClaim,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_history_reader import (
    FakeAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.unexplained_position import (
    PositionUnexplainedWhy,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    position_explainer,
    single_venue_scopes,
    venue_context,
)

_FUTURES = TradingVenue.FUTURES_TESTNET
_CLAIM = OwnerPositionClaim("bot-f0", TAG, "BTCUSDT", RUN)


def _live(symbol: str, amount: str) -> LivePosition:
    return LivePosition(
        symbol,
        Decimal(amount),
        Decimal(60000),
        Decimal(60000),
        Decimal(0),
        10,
        MarginType.ISOLATED,
        LiquidationPrice(Decimal(50000)),
        NOW,
    )


def _metadata(fails: Exception | None = None) -> Mock:
    provider = Mock(spec=IMarketMetadataProvider)
    provider.get_or_fetch.return_value = SymbolOrderMetadata(
        "BTCUSDT", "TRADING", STEP, Decimal("0.1"), Decimal(5), 3, 1, NOW
    )
    provider.get_or_fetch.side_effect = fails
    return provider


def _judged(
    positions: tuple[LivePosition, ...],
    claims: tuple[OwnerPositionClaim, ...],
    *fills: tuple[object, object],
    explainer: PositionExplainer | None = None,
    metadata: Mock | None = None,
    history: FakeAccountHistoryReader | None = None,
):  # type: ignore[no-untyped-def]
    context = venue_context(
        _FUTURES,
        metadata_provider=metadata or _metadata(),
        history_reader=history  # type: ignore[arg-type]
        or FakeAccountHistoryReader(
            [o for o, _ in fills],  # type: ignore[misc]
            [t for _, t in fills],  # type: ignore[misc]
            now=NOW,
        ),
    )
    scope = single_venue_scopes(context).get(_FUTURES)
    return (explainer or position_explainer()).unexplained(scope, positions, claims)


def test_a_position_the_claims_tagged_history_adds_up_to_is_excused() -> None:
    found = _judged(
        (_live("BTCUSDT", "0.020"),),
        (_CLAIM,),
        traded(1, OrderSide.BUY, "0.010", "60000"),
        traded(2, OrderSide.BUY, "0.010", "61000"),
    )

    assert found == ()


def test_fills_that_landed_while_the_host_was_down_are_part_of_the_history() -> None:
    """The exchange's history is the evidence, not the bot's file: a fill nobody heard still counts."""
    found = _judged(
        (_live("BTCUSDT", "0.016"),),
        (_CLAIM,),
        traded(1, OrderSide.BUY, "0.010", "60000"),
        traded(2, OrderSide.BUY, "0.010", "59000"),
        traded(3, OrderSide.SELL, "0.004", "61000"),
    )

    assert found == ()


def test_a_position_within_one_step_of_the_history_is_excused_and_one_beyond_it_is_not() -> (
    None
):
    buy = traded(1, OrderSide.BUY, "0.010", "60000")

    assert _judged((_live("BTCUSDT", "0.011"),), (_CLAIM,), buy) == ()
    beyond = _judged((_live("BTCUSDT", "0.012"),), (_CLAIM,), buy)
    assert [p.why for p in beyond] == [PositionUnexplainedWhy.DIFFERS_FROM_HISTORY]
    assert (beyond[0].exchange_quantity, beyond[0].derived_quantity) == (
        Decimal("0.012"),
        Decimal("0.010"),
    )


def test_less_than_the_history_explains_is_not_excused_either() -> None:
    found = _judged(
        (_live("BTCUSDT", "0.004"),),
        (_CLAIM,),
        traded(1, OrderSide.BUY, "0.010", "60000"),
    )

    assert [p.why for p in found] == [PositionUnexplainedWhy.DIFFERS_FROM_HISTORY]


def test_a_short_the_claims_sells_built_is_excused() -> None:
    found = _judged(
        (_live("BTCUSDT", "-0.010"),),
        (_CLAIM,),
        traded(1, OrderSide.SELL, "0.010", "60000"),
    )

    assert found == ()


def test_the_opposite_side_is_not_excused() -> None:
    found = _judged(
        (_live("BTCUSDT", "-0.010"),),
        (_CLAIM,),
        traded(1, OrderSide.BUY, "0.010", "60000"),
    )

    assert [p.why for p in found] == [PositionUnexplainedWhy.DIFFERS_FROM_HISTORY]


def test_a_symbol_no_claim_names_is_a_stray_with_its_figures() -> None:
    found = _judged((_live("ETHUSDT", "0.300"),), (_CLAIM,))

    assert [(p.symbol, p.exchange_quantity, p.why) for p in found] == [
        ("ETHUSDT", Decimal("0.300"), PositionUnexplainedWhy.NO_CLAIM)
    ]


def test_no_claims_names_every_position() -> None:
    """A Start, an arm and a manual order pass no claim: every position of the account refuses."""
    found = _judged((_live("BTCUSDT", "0.010"), _live("ETHUSDT", "0.300")), ())

    assert [p.why for p in found] == [PositionUnexplainedWhy.NO_CLAIM] * 2


def test_the_claim_of_another_run_started_after_the_fills_explains_nothing() -> None:
    """Fills before `run_started_at` are not the run's: a later run's claim cannot excuse them."""
    later = OwnerPositionClaim("bot-f0", TAG, "BTCUSDT", NOW)
    found = _judged(
        (_live("BTCUSDT", "0.010"),),
        (later,),
        traded(1, OrderSide.BUY, "0.010", "60000"),
    )

    assert [p.why for p in found] == [PositionUnexplainedWhy.DIFFERS_FROM_HISTORY]


class _ReadsCounted(FakeAccountHistoryReader):
    """A history that counts what was asked of it, and can be made to fail."""

    def __init__(self, fails: Exception | None = None) -> None:
        super().__init__(now=NOW)
        self.reads = 0
        self._fails = fails

    def order_history(self, symbol: str, since: datetime):  # type: ignore[no-untyped-def]
        self.reads += 1
        if self._fails is not None:
            raise self._fails
        return super().order_history(symbol, since)


def test_only_the_account_positions_are_judged_so_a_flat_claim_costs_no_read() -> None:
    history = _ReadsCounted()

    found = _judged((), (_CLAIM,), history=history)

    assert found == ()
    assert history.reads == 0


def test_a_claim_whose_history_cannot_be_read_does_not_excuse_the_position() -> None:
    found = _judged(
        (_live("BTCUSDT", "0.010"),),
        (_CLAIM,),
        history=_ReadsCounted(AccountHistoryUnavailableError("down")),
    )

    assert [p.why for p in found] == [PositionUnexplainedWhy.HISTORY_UNVERIFIABLE]


def test_a_symbol_whose_rules_cannot_be_read_does_not_excuse_the_position() -> None:
    found = _judged(
        (_live("BTCUSDT", "0.010"),),
        (_CLAIM,),
        metadata=_metadata(SymbolRulesUnavailableError("BTCUSDT")),
    )

    assert [p.why for p in found] == [PositionUnexplainedWhy.HISTORY_UNVERIFIABLE]


def test_a_history_further_back_than_the_venue_keeps_it_is_unverifiable() -> None:
    old = OwnerPositionClaim("bot-f0", TAG, "BTCUSDT", NOW.replace(year=NOW.year - 1))

    found = _judged((_live("BTCUSDT", "0.010"),), (old,))

    assert [p.why for p in found] == [PositionUnexplainedWhy.HISTORY_UNVERIFIABLE]


def test_every_position_of_the_account_needs_its_own_explanation() -> None:
    """One explained symbol does not excuse a stray beside it: the opening is venue-wide."""
    found = _judged(
        (_live("BTCUSDT", "0.010"), _live("ETHUSDT", "0.300")),
        (_CLAIM,),
        traded(1, OrderSide.BUY, "0.010", "60000"),
    )

    assert [(p.symbol, p.why) for p in found] == [
        ("ETHUSDT", PositionUnexplainedWhy.NO_CLAIM)
    ]
