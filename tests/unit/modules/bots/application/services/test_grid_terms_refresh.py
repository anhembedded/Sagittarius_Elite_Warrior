"""`EPIC-035U` (L5) — a filter the exchange changes mid-run halts the bot by name.

The symbol's filters were read once per executor, from a catalog the venue keeps
for a day. A tick size that changed after Start surfaced as `-1013` on a later
order and the bot went to ERROR. Now a bot that holds orders asks the exchange for
its terms on an interval, and a change halts it with the old and new values.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_terms_watch import (
    TERMS_REFRESH_EVERY_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_catalog_unreachable_error import (
    SymbolCatalogUnreachableError,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    SYMBOL,
    GridWorld,
    grid_world,
    terms_entry,
)

S = BotLifecycleState


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    assert world.state() is S.RUNNING
    world.executor.facts.on_tick(PriceTick.at(Decimal(121)))
    return world


def _beats(world: GridWorld, seconds: float, every: float = 30.0) -> None:
    """The price watch's heartbeat for `seconds`, the feed alive throughout."""
    elapsed = 0.0
    while elapsed < seconds:
        world.monotonic.advance(every)
        elapsed += every
        world.executor.facts.on_tick(PriceTick.at(Decimal(121)))
        world.executor.facts.on_price_age_check()


def test_a_tick_size_change_halts_the_bot_with_the_old_and_new_values() -> None:
    world = _running()
    world.terms.answer_with(terms_entry(tick="0.001"))

    _beats(world, TERMS_REFRESH_EVERY_SECONDS)

    assert world.state() is S.HALTED
    runtime = world.runtime()
    assert runtime.reason is GridReason.EXCHANGE_TERMS_CHANGED
    assert "tick size 0.01 -> 0.001" in runtime.reason_detail
    assert SYMBOL in runtime.reason_detail
    assert world.book.open == {}, "the guard took the ladder off the exchange"


def test_a_minimum_notional_change_is_named_too() -> None:
    world = _running()
    world.terms.answer_with(terms_entry(min_notional="10"))

    _beats(world, TERMS_REFRESH_EVERY_SECONDS)

    assert world.runtime().reason is GridReason.EXCHANGE_TERMS_CHANGED
    assert "minimum notional 5 -> 10" in world.runtime().reason_detail


def test_unchanged_terms_are_asked_for_again_and_change_nothing() -> None:
    world = _running()
    asked = len(world.terms.fresh_reads)

    _beats(world, TERMS_REFRESH_EVERY_SECONDS)

    assert len(world.terms.fresh_reads) == asked + 1, "read from the exchange, once"
    assert world.state() is S.RUNNING
    assert world.book.open, "the ladder is where it was"


def test_the_terms_are_not_asked_for_before_the_interval_has_passed() -> None:
    world = _running()
    asked = len(world.terms.fresh_reads)

    _beats(world, TERMS_REFRESH_EVERY_SECONDS / 2)

    assert len(world.terms.fresh_reads) == asked


def test_a_changed_fee_halts_nothing() -> None:
    world = _running()
    world.terms.answer_with(terms_entry(maker="0.00075"))

    _beats(world, TERMS_REFRESH_EVERY_SECONDS)

    assert world.state() is S.RUNNING
    assert world.book.open


def test_a_symbol_the_exchange_stopped_listing_halts_the_bot_by_name() -> None:
    world = _running()
    world.terms.unlist(SYMBOL)

    _beats(world, TERMS_REFRESH_EVERY_SECONDS)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.SYMBOL_DELISTED


def test_a_failed_read_halts_nothing_and_is_asked_again_at_the_next_interval() -> None:
    world = _running()
    world.terms.fail_fresh_reads_with(RuntimeError("exchangeInfo timed out"))

    _beats(world, TERMS_REFRESH_EVERY_SECONDS)

    assert world.state() is S.RUNNING
    world.terms.fail_fresh_reads_with(None)
    world.terms.answer_with(terms_entry(tick="0.001"))
    _beats(world, TERMS_REFRESH_EVERY_SECONDS)
    assert world.runtime().reason is GridReason.EXCHANGE_TERMS_CHANGED


def test_a_catalog_that_could_not_be_read_is_not_a_delisting() -> None:
    """The catalog fetch raises `SymbolRulesUnavailableError` for a timeout too;
    a healthy bot must not halt for one bad moment (the reviewer's finding)."""
    world = _running()
    world.terms.fail_fresh_reads_with(SymbolCatalogUnreachableError("timed out"))

    _beats(world, TERMS_REFRESH_EVERY_SECONDS)

    assert world.state() is S.RUNNING
    assert world.book.open, "the ladder is where it was"
    world.terms.fail_fresh_reads_with(None)
    world.terms.answer_with(terms_entry(tick="0.001"))
    _beats(world, TERMS_REFRESH_EVERY_SECONDS)
    assert world.runtime().reason is GridReason.EXCHANGE_TERMS_CHANGED


def test_a_start_whose_terms_read_failed_in_transit_is_not_called_a_delisting() -> None:
    world = grid_world()
    world.terms.fail_fresh_reads_with(SymbolCatalogUnreachableError("timed out"))

    world.executor.start()

    # The terms held (first read, from the catalog) still say TRADING, so the start
    # goes on instead of refusing for a bad moment; the exchange's own refusal of
    # an order remains the guard.
    assert world.state() is S.RUNNING
    assert world.runtime().reason is None
