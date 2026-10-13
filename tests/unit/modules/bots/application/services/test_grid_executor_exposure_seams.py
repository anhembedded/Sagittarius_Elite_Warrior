"""`EPIC-039H` — the four exposure joints of a Grid executor are ports, and the sequences use them.

@details The Spot behaviour is proven by the whole executor suite, unchanged. This file proves
the other half: that a venue profile with another exposure is **one table entry**, because the
start, the stop, the reconcile and the ladder reach the opening, the close, the check and the
flags only through `GridExposure`. The collaborators here are substitutes written from the four
ports, shaped like a position venue's (no opening buy, reduce-only SELLs, a close that sends
nothing), and the executor is the real one over the simulated venue.

Retire when: the position venue's own journeys on the Futures fake (`EPIC-039H`) cover each
joint end to end and a test per joint there goes red when the joint is bypassed.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.closer_spot import (
    SpotExposureCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.exposure_check_spot import (
    SpotExposureCheck,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_exposures import (
    ExposureKindNotBuiltError,
    GridExposure,
    GridExposures,
    spot_exposure,
    spot_only_exposures,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.opening_spot import (
    SpotOpening,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.order_flags_spot import (
    SpotOrderFlags,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue_profiles_by_market import (
    VenueProfilesByMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_check import (
    ExposureMismatch,
    IExposureCheck,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_closer import (
    IExposureCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_opening_strategy import (
    IOpeningStrategy,
    OpeningResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_flags import (
    IOrderFlags,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.stop_progress import (
    StopProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    LAST_PRICE,
    grid_world,
    recovering_world,
)

S = BotLifecycleState


class _OpensNothing(IOpeningStrategy):
    def __init__(self) -> None:
        self.opened: list[GridPlan] = []

    def open(self, plan: GridPlan) -> OpeningResult:
        self.opened.append(plan)
        return OpeningResult(plan)


class _RefusesToOpen(IOpeningStrategy):
    def open(self, plan: GridPlan) -> OpeningResult:
        return OpeningResult(None)


class _ClosesNothing(IExposureCloser):
    def __init__(self) -> None:
        self.closed: list[tuple[OwnerBudgetRegistrationResult, Decimal]] = []

    def closes_on_halt(self) -> bool:
        return False

    def close(
        self, registration: OwnerBudgetRegistrationResult, price: Decimal
    ) -> StopProgress | None:
        self.closed.append((registration, price))
        return None


class _ClosesOnHalt(_ClosesNothing):
    def closes_on_halt(self) -> bool:
        return True


class _SellsAreReduceOnly(IOrderFlags):
    def reduce_only(self, side: OrderSide) -> bool:
        return side is OrderSide.SELL


class _FindsADifference(IExposureCheck):
    def derives(self, registration: OwnerBudgetRegistrationResult) -> bool:
        return True

    def held(
        self, registration: OwnerBudgetRegistrationResult
    ) -> OwnerInventory | None:
        return registration.inventory

    def check(
        self, runtime: GridRuntime, registration: OwnerBudgetRegistrationResult
    ) -> ExposureMismatch | None:
        return ExposureMismatch(GridReason.POSITION_MISMATCH, "the exchange holds 3")


def _exposures(
    *,
    opening: IOpeningStrategy | None = None,
    closer: IExposureCloser | None = None,
    check: IExposureCheck | None = None,
    flags: IOrderFlags | None = None,
) -> GridExposures:
    def build(context: GridRunContext) -> GridExposure:
        spot = spot_exposure(context)
        return GridExposure(
            opening or spot.opening,
            closer or spot.closer,
            check or spot.check,
            flags or spot.flags,
        )

    return GridExposures(VenueProfilesByMarket(), {ExposureKind.INVENTORY: build})


def test_the_spot_table_builds_the_spot_collaborators_for_a_spot_bot() -> None:
    world = grid_world()
    context = world.executor._context

    built = spot_only_exposures().build(context)

    assert isinstance(built.opening, SpotOpening)
    assert isinstance(built.closer, SpotExposureCloser)
    assert isinstance(built.check, SpotExposureCheck)
    assert isinstance(built.flags, SpotOrderFlags)


def test_an_exposure_kind_with_no_builder_is_not_silently_given_spots() -> None:
    world = grid_world()
    only_positions = GridExposures(
        VenueProfilesByMarket(), {ExposureKind.POSITION: spot_exposure}
    )

    with pytest.raises(ExposureKindNotBuiltError) as refused:
        only_positions.build(world.executor._context)

    assert "INVENTORY" in str(refused.value)
    assert "no collaborators" in str(refused.value)


def test_the_start_takes_its_opening_from_the_strategy_and_lays_what_it_returns() -> (
    None
):
    opening = _OpensNothing()
    world = grid_world(exposures=_exposures(opening=opening))

    world.executor.start()

    assert len(opening.opened) == 1
    assert [r for r in world.book.requests if r.order_type is OrderType.MARKET] == []
    assert len(world.book.open) == 4
    assert world.state() is S.RUNNING


def test_a_start_whose_opening_does_not_proceed_lays_nothing() -> None:
    world = grid_world(exposures=_exposures(opening=_RefusesToOpen()))

    world.executor.start()

    assert world.book.requests == []
    assert world.state() is S.STARTING


def test_every_ladder_order_carries_the_flag_the_venue_profile_gives_it() -> None:
    world = grid_world(
        exposures=_exposures(opening=_OpensNothing(), flags=_SellsAreReduceOnly())
    )
    world.executor.start()

    laid = {r.side: r.reduce_only for r in world.book.requests}
    assert laid == {OrderSide.SELL: True, OrderSide.BUY: False}

    whole = world.book.open[world.open_ids_by_price()[Decimal(110)]].quantity
    world.fill(Decimal(110), str(whole))  # a BUY fills: its counter is a SELL one up
    counters = [r for r in world.book.requests[4:] if r.side is OrderSide.SELL]
    assert counters
    assert all(r.reduce_only for r in counters)


def test_the_stop_hands_the_close_to_the_closer_and_sells_nothing_itself() -> None:
    closer = _ClosesNothing()
    world = grid_world(exposures=_exposures(opening=_OpensNothing(), closer=closer))
    world.executor.start()
    sent = len(world.book.requests)
    world.derive("2")

    world.executor.stop(ExposureHandling.CLOSE_AT_MARKET)

    assert world.state() is S.STOPPED
    ((registration, price),) = closer.closed
    assert registration.inventory is not None
    assert registration.inventory.quantity == Decimal(2)
    assert price == LAST_PRICE
    assert len(world.book.requests) == sent  # no market SELL came from the sequence


def test_a_stop_that_keeps_the_exposure_does_not_ask_the_closer() -> None:
    closer = _ClosesNothing()
    world = grid_world(exposures=_exposures(opening=_OpensNothing(), closer=closer))
    world.executor.start()

    world.executor.stop(ExposureHandling.KEEP)

    assert closer.closed == []
    assert world.state() is S.STOPPED


def test_a_reconcile_halts_with_the_reason_the_exposure_check_names() -> None:
    world = recovering_world(exposures=_exposures(check=_FindsADifference()))

    world.executor.facts.on_switch(True, TradingSwitchCause.ENABLED)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.POSITION_MISMATCH
    assert "the exchange holds 3" in world.runtime().reason_detail


def test_a_halt_takes_the_ladder_off_and_then_stops_with_the_close_when_the_venue_closes_on_halt() -> (
    None
):
    """`EPIC-039H` (O8): a halt on a venue whose exposure is a leveraged position ends in the
    same stop the user's Stop runs, so one tested close serves both; the halt's reason is kept."""
    closer = _ClosesOnHalt()
    world = grid_world(exposures=_exposures(opening=_OpensNothing(), closer=closer))
    world.executor.start()
    world.derive("2")

    world.executor.facts.halt_user_stream_down(timedelta(seconds=130))

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.USER_STREAM_DOWN
    assert "never left bare" in world.runtime().reason_detail
    assert world.book.open == {}
    ((registration, _price),) = closer.closed
    assert registration.inventory is not None and registration.inventory.quantity == 2


def test_a_halt_on_a_venue_that_does_not_close_on_halt_leaves_what_it_holds() -> None:
    closer = _ClosesNothing()
    world = grid_world(exposures=_exposures(opening=_OpensNothing(), closer=closer))
    world.executor.start()

    world.executor.facts.halt_user_stream_down(timedelta(seconds=130))

    assert world.state() is S.HALTED
    assert closer.closed == []
    assert world.book.open == {}, "the ladder is off, the exposure is the user's"
