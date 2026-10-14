"""`EPIC-039H` - the position venue's collaborators of a Grid executor, one by one.

@details The journeys on the Futures fake (`tests/integration/modules/bots`) prove the whole path.
These pin the decisions each collaborator makes alone: which orders are reduce-only, what a
reconcile calls a mismatch, what a position budget may reach, what the symbol's brackets cap it
at, and that a registration returning a divergence is never traded on.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_budgets import (
    FuturesGridBudgets,
    GridBudgetsByProfile,
    SpotGridBudgets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.order_flags_futures import (
    PositionOrderFlags,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.positions.exposure_check_futures import (
    PositionExposureCheck,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.symbol_brackets import (
    BracketsUnavailableError,
    SymbolBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.venue_profiles_by_market import (
    VenueProfilesByMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
    OwnerBudget,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    OwnerPosition,
    PositionDivergence,
    PositionDivergenceKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
    FuturesReads,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.futures_world import (
    BRACKETS,
    SYMBOL,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    grid_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
)

D = Decimal
_FUTURES = TradingVenue.FUTURES_TESTNET
_LONG = {**CONFIG, "direction": "LONG", "leverage": "3", "stop_loss": "price:50000"}


# --- the flags: only an exit is reduce-only -----------------------------------


@pytest.mark.parametrize(
    ("direction", "reduces"),
    [
        (TradeDirection.LONG, OrderSide.SELL),
        (TradeDirection.SHORT, OrderSide.BUY),
    ],
)
def test_the_order_that_exits_the_position_is_reduce_only_and_the_other_is_not(
    direction: TradeDirection, reduces: OrderSide
) -> None:
    flags = PositionOrderFlags(direction)
    entering = OrderSide.BUY if reduces is OrderSide.SELL else OrderSide.SELL

    assert flags.reduce_only(reduces) is True
    assert flags.reduce_only(entering) is False


def test_a_neutral_grids_orders_can_open_on_either_side_so_none_is_reduce_only() -> (
    None
):
    flags = PositionOrderFlags(TradeDirection.NEUTRAL)

    assert not flags.reduce_only(OrderSide.BUY)
    assert not flags.reduce_only(OrderSide.SELL)


# --- the reconcile check ------------------------------------------------------


def _check() -> PositionExposureCheck:
    world = grid_world()
    return PositionExposureCheck(world.executor._context)


def _registered(
    quantity: str, divergence: PositionDivergence | None = None
) -> OwnerBudgetRegistrationResult:
    position = OwnerPosition(
        D(quantity), D(60_000) if D(quantity) else None, D(0), D(0)
    )
    return OwnerBudgetRegistrationResult(None, position=position, divergence=divergence)


def _runtime(inventory: str) -> GridRuntime:
    return GridRuntime((), inventory=D(inventory))


def _divergence(kind: PositionDivergenceKind) -> PositionDivergence:
    return PositionDivergence(kind, "bot.abc", "abc", "BTCUSDT", D("0.05"), D("0.08"))


def test_a_position_that_agrees_to_within_a_step_is_no_mismatch() -> None:
    check = _check()

    assert check.check(_runtime("0.0500"), _registered("0.0504")) is None


def test_a_position_that_differs_by_more_than_a_step_is_a_position_mismatch() -> None:
    mismatch = _check().check(_runtime("0.05"), _registered("0.07"))

    assert mismatch is not None
    assert mismatch.reason is GridReason.POSITION_MISMATCH
    assert "0.05" in mismatch.detail and "0.07" in mismatch.detail


@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        (PositionDivergenceKind.POSITION_CHANGED_UNORDERED, GridReason.FOREIGN_FILL),
        (PositionDivergenceKind.POSITION_MISMATCH, GridReason.POSITION_MISMATCH),
    ],
)
def test_a_registration_that_returned_a_divergence_is_never_reconciled_over(
    kind: PositionDivergenceKind, reason: GridReason
) -> None:
    """The ladder's own count agrees with the derivation, and still: the exchange disagrees."""
    mismatch = _check().check(_runtime("0.05"), _registered("0.05", _divergence(kind)))

    assert mismatch is not None
    assert mismatch.reason is reason


def test_a_registration_without_a_position_is_not_a_position_registration() -> None:
    check = _check()
    spots = OwnerBudgetRegistrationResult(None, OwnerInventory(D(1), D(1)))

    assert check.derives(spots) is False
    assert check.derives(_registered("0.05")) is True
    with pytest.raises(ValueError, match="no position"):
        check.check(_runtime("0"), spots)


def test_what_a_resume_sizes_to_is_the_long_position_and_its_notional_at_entry() -> (
    None
):
    check = _check()

    assert check.held(_registered("0.05")) == OwnerInventory(D("0.05"), D("3000"))
    assert check.held(_registered("0")) == OwnerInventory(D(0), D(0))
    assert check.held(_registered("-0.05")) is None, "a short has no such reading"
    assert check.held(OwnerBudgetRegistrationResult(None)) is None


# --- the owner budget ---------------------------------------------------------


def _brackets() -> SymbolBrackets:
    ports = FakeVenueTradingPorts(
        fake_venue_ports(
            _FUTURES,
            order_entry_terms=FakeOrderEntryTerms(
                futures=FuturesReads(brackets={SYMBOL: BRACKETS})
            ),
        )
    )
    return SymbolBrackets(ports)


def test_a_position_budget_reaches_the_margin_times_the_leverage() -> None:
    params = GridParams.from_config({**_LONG, "capital_quote": "1000"})
    budgets = FuturesGridBudgets(DEFAULT_OWNER_BUDGET_CAPS, _brackets())

    budget = budgets.budget_of(_FUTURES, SYMBOL, params)

    assert budget.futures is not None
    assert (budget.futures.max_position_notional, budget.futures.leverage) == (
        D(3000),
        3,
    )
    assert budget.futures.committed_margin == D(1000)


def test_a_position_budget_never_exceeds_what_the_brackets_allow_at_the_leverage() -> (
    None
):
    """`BRACKETS` allow 20x up to 50,000 and 10x up to 250,000: 15x may reach 50,000 only."""
    params = GridParams.from_config(
        {**_LONG, "capital_quote": "10000", "leverage": "15"}
    )
    budgets = FuturesGridBudgets(DEFAULT_OWNER_BUDGET_CAPS, _brackets())

    budget = budgets.budget_of(_FUTURES, SYMBOL, params)

    assert budget.futures is not None
    assert budget.futures.max_position_notional == D(50_000)


def test_a_leverage_no_bracket_allows_is_not_given_a_ceiling_of_its_own() -> None:
    """The plan-time guard and the readiness rule refuse such a ladder before an order."""
    params = GridParams.from_config(
        {**_LONG, "capital_quote": "1000", "leverage": "50"}
    )

    budget = FuturesGridBudgets(DEFAULT_OWNER_BUDGET_CAPS, _brackets()).budget_of(
        _FUTURES, SYMBOL, params
    )

    assert budget.futures is not None
    assert budget.futures.max_position_notional == D(50_000)


def test_the_brackets_are_read_once_and_again_only_when_asked() -> None:
    brackets = _brackets()

    first = brackets.get(_FUTURES, SYMBOL)

    assert brackets.get(_FUTURES, SYMBOL) is first
    assert brackets.refresh(_FUTURES, SYMBOL) == first


def test_a_venue_with_no_brackets_says_so() -> None:
    ports = FakeVenueTradingPorts(
        fake_venue_ports(
            TradingVenue.SPOT_TESTNET,
            order_entry_terms=FakeOrderEntryTerms(
                futures=FuturesReads(brackets={SYMBOL: NotApplicable.ON_THIS_VENUE})
            ),
        )
    )

    with pytest.raises(BracketsUnavailableError):
        SymbolBrackets(ports).get(TradingVenue.SPOT_TESTNET, SYMBOL)


def test_the_budget_of_a_spot_bot_has_no_position_limits_and_is_unchanged() -> None:
    params = GridParams.from_config(CONFIG)
    by_profile = GridBudgetsByProfile(
        VenueProfilesByMarket(),
        {
            ExposureKind.INVENTORY: SpotGridBudgets(DEFAULT_OWNER_BUDGET_CAPS),
            ExposureKind.POSITION: FuturesGridBudgets(
                DEFAULT_OWNER_BUDGET_CAPS, _brackets()
            ),
        },
    )

    spot = by_profile.budget_of(TradingVenue.SPOT_TESTNET, "BTCUSDT", params)
    futures = by_profile.budget_of(_FUTURES, SYMBOL, params)

    assert isinstance(spot, OwnerBudget) and spot.futures is None
    assert spot.max_exposure_quote == params.capital_quote
    assert futures.futures is not None
