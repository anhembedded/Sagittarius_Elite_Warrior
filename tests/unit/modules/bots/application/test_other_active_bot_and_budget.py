"""`EPIC-034H`, `EPIC-029J` J1b — the facts the Run step reads before the click: which other bot
holds the symbol, whether the venue is full (ADR D20), and whether the owner budget fits
trading's caps."""

from __future__ import annotations

from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_budget import (
    grid_budget_problem,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.other_active_bot import (
    BotSlot,
    VenueOccupancy,
    occupancy_of,
    other_active_bot,
    venue_is_full,
    venue_recovering,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RUN_STARTING_STATES,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.venue_bot_cap import (
    MAX_ACTIVE_BOTS_PER_VENUE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    CONFIG,
)

S = BotLifecycleState
_ACTIVE = [s for s in S if s not in RUN_STARTING_STATES]


SPOT = TradingVenue.SPOT_TESTNET
FUTURES = TradingVenue.FUTURES_TESTNET
BTC = "BTCUSDT"
ETH = "ETHUSDT"


def _slot(bot_id: str, venue: TradingVenue, symbol: str, state: S) -> BotSlot:
    return BotSlot(bot_id, venue, symbol, state)


@pytest.mark.parametrize("state", _ACTIVE)
def test_every_state_a_new_run_does_not_start_from_is_active(state: S) -> None:
    slots = [_slot("a", SPOT, BTC, state), _slot("b", SPOT, BTC, S.DRAFT)]

    assert other_active_bot("b", SPOT, BTC, slots) == "a"


@pytest.mark.parametrize("state", sorted(RUN_STARTING_STATES, key=lambda s: s.value))
def test_a_bot_at_rest_is_not_active(state: S) -> None:
    assert other_active_bot("b", SPOT, BTC, [_slot("a", SPOT, BTC, state)]) == ""


def test_the_bot_itself_is_never_another_bot() -> None:
    assert other_active_bot("a", SPOT, BTC, [_slot("a", SPOT, BTC, S.RUNNING)]) == ""


@pytest.mark.parametrize("state", _ACTIVE)
def test_an_active_bot_of_another_venue_does_not_block(state: S) -> None:
    """`EPIC-029J` J1a: bots on different venues run together."""
    assert other_active_bot("b", FUTURES, BTC, [_slot("a", SPOT, BTC, state)]) == ""


@pytest.mark.parametrize("state", _ACTIVE)
def test_an_active_bot_on_another_symbol_of_the_venue_does_not_block(state: S) -> None:
    """`EPIC-029J` J1b: the symbol, not the venue, is what two bots cannot share."""
    assert other_active_bot("b", SPOT, ETH, [_slot("a", SPOT, BTC, state)]) == ""


def test_only_the_bot_on_the_same_venue_and_symbol_is_named() -> None:
    slots = [
        _slot("a", SPOT, BTC, S.RUNNING),
        _slot("c", FUTURES, BTC, S.HALTED),
        _slot("d", FUTURES, ETH, S.RUNNING),
    ]

    assert other_active_bot("b", FUTURES, BTC, slots) == "c"
    assert other_active_bot("b", SPOT, BTC, slots) == "a"
    assert other_active_bot("b", FUTURES, ETH, slots) == "d"
    assert other_active_bot("b", SPOT, ETH, slots) == ""


def test_a_refused_file_holds_every_symbol_unless_it_is_the_bots_own() -> None:
    """Its venue and symbol are unknown, so it is the worst case: it may hold any."""
    for venue in (SPOT, FUTURES):
        assert other_active_bot("b", venue, BTC, [], ["a.json"]) == "a.json"
        assert other_active_bot("b", venue, ETH, [], ["a.json"]) == "a.json"
        assert other_active_bot("b", venue, BTC, [], ["b.json"]) == ""


def _crowd(count: int, venue: TradingVenue = FUTURES) -> list[BotSlot]:
    return [
        _slot(f"x{index}", venue, f"S{index}USDT", S.RUNNING) for index in range(count)
    ]


def test_a_venue_below_the_cap_has_room() -> None:
    assert venue_is_full("b", FUTURES, _crowd(MAX_ACTIVE_BOTS_PER_VENUE - 1)) == ()


def test_a_venue_at_the_cap_is_full_and_names_the_bots_that_fill_it() -> None:
    crowd = _crowd(MAX_ACTIVE_BOTS_PER_VENUE)

    assert venue_is_full("b", FUTURES, crowd) == tuple(slot.bot_id for slot in crowd)


def test_a_bot_already_among_the_active_ones_does_not_count_against_itself() -> None:
    """A bot that is itself active (a resume, a reconcile) asks whether *another* may join."""
    crowd = _crowd(MAX_ACTIVE_BOTS_PER_VENUE)

    assert venue_is_full(crowd[0].bot_id, FUTURES, crowd) == ()


def test_the_cap_counts_one_venue_and_only_active_bots() -> None:
    other_venue = _crowd(MAX_ACTIVE_BOTS_PER_VENUE, SPOT)
    at_rest = [
        _slot(f"r{index}", FUTURES, f"R{index}USDT", S.STOPPED)
        for index in range(MAX_ACTIVE_BOTS_PER_VENUE)
    ]

    assert venue_is_full("b", FUTURES, other_venue + at_rest) == ()


def test_a_recovering_bot_of_the_venue_is_named_whatever_its_symbol() -> None:
    """A RECOVERING bot is reconciled only by its own Resume (`BOT-183`, `BOT-201`), so a Start waits
    for every one of the venue, whatever its symbol."""
    slots = [
        _slot("a", FUTURES, BTC, S.RECOVERING),
        _slot("c", FUTURES, ETH, S.RUNNING),
        _slot("d", SPOT, BTC, S.RECOVERING),
        _slot("e", FUTURES, "XRPUSDT", S.RECOVERING),
    ]

    assert venue_recovering("b", FUTURES, slots) == ("a", "e")
    assert venue_recovering("b", SPOT, slots) == ("d",)


def test_a_recovering_bot_is_not_waiting_on_itself() -> None:
    assert (
        venue_recovering("a", FUTURES, [_slot("a", FUTURES, BTC, S.RECOVERING)]) == ()
    )


@pytest.mark.parametrize("state", [s for s in S if s is not S.RECOVERING])
def test_only_a_recovering_bot_holds_the_start_back(state: S) -> None:
    assert venue_recovering("b", FUTURES, [_slot("a", FUTURES, BTC, state)]) == ()


def test_the_occupancy_is_the_three_answers_read_once() -> None:
    slots = [
        _slot("a", FUTURES, BTC, S.RECOVERING),
        _slot("c", FUTURES, ETH, S.RUNNING),
    ]

    occupancy = occupancy_of("b", FUTURES, BTC, slots)

    assert occupancy == VenueOccupancy("a", (), ("a",))


def test_a_ladder_within_the_caps_has_no_budget_problem() -> None:
    assert grid_budget_problem(CONFIG, DEFAULT_OWNER_BUDGET_CAPS) == ""


def test_a_ladder_one_order_past_the_cap_names_both_numbers() -> None:
    """Four grids keep five orders open; a cap of four refuses it."""
    caps = replace(DEFAULT_OWNER_BUDGET_CAPS, max_open_orders=4)

    problem = grid_budget_problem(CONFIG, caps)

    assert "5 orders" in problem
    assert "at most 4" in problem


def test_a_ladder_exactly_at_the_cap_passes() -> None:
    caps = replace(DEFAULT_OWNER_BUDGET_CAPS, max_open_orders=5)

    assert grid_budget_problem(CONFIG, caps) == ""


def test_parameters_that_cannot_be_read_are_the_design_steps_to_say() -> None:
    assert grid_budget_problem({"lower": "x"}, DEFAULT_OWNER_BUDGET_CAPS) == ""
