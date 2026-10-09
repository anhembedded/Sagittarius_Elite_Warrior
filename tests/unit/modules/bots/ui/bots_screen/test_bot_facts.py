"""`EPIC-029F` — the detail panel's figures."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_pnl import (
    PnlSummary,
    pnl_summary,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    NO_VALUE,
    bot_facts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_plan_panel import (
    FACT_SPECS,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.grid_runtime_builders import (
    started_ladder,
)

from .bots_screen_fixtures import NOW, stored

_HELD = BotProgress(
    realised_profit=Decimal("12.5"),
    completed_cycles=3,
    open_orders=2,
    inventory=Decimal("0.01"),
    average_cost=Decimal(64000),
    reason="switch_off",
    reason_detail="trading turned off",
)


def _running(progress: BotProgress | None = _HELD) -> BotSnapshot:
    return BotSnapshot.of(stored("a00001", BotLifecycleState.HALTED).bot, progress)


def _pnl(
    mark: str | None, inventory: str = "0.01", realised_total: str = "20"
) -> PnlSummary:
    runtime = GridRuntime(
        started_ladder().levels,
        inventory=Decimal(inventory),
        cost=Decimal(inventory) * 64000,
        realised_profit=Decimal("12.5"),
        realised_total=Decimal(realised_total),
        start_price=Decimal(60000),
        mark_price=Decimal(mark) if mark else None,
    )
    return pnl_summary(runtime, capital=Decimal(1000))


_PRICED = replace(_HELD, mark_price=Decimal(65000), pnl=_pnl("65000"))


def test_unrealised_pnl_is_what_the_held_base_gained_at_the_bots_own_price() -> None:
    facts = bot_facts(_running(_PRICED), NOW)

    assert facts.unrealised == "10.00 at 65,000.00"
    lower = replace(_PRICED, mark_price=Decimal(63000), pnl=_pnl("63000"))
    assert bot_facts(_running(lower), NOW).unrealised == "-10.00 at 63,000.00"


def test_the_total_is_the_first_figure_with_grid_profit_as_one_part_of_it() -> None:
    facts = bot_facts(_running(_PRICED), NOW)

    assert facts.total_pnl == "30.00"
    assert facts.grid_profit == "12.50"
    shown = [spec.key for spec in FACT_SPECS]
    assert shown[shown.index("total_pnl") :][:3] == [
        "total_pnl",
        "grid_profit",
        "unrealised",
    ]


def test_the_hodl_benchmark_is_shown_beside_the_total() -> None:
    """1000 at 60 000 buys 1/60 BTC; at 65 000 that is 1083.33: +83.33."""
    assert bot_facts(_running(_PRICED), NOW).hodl == "83.33"


def test_without_a_price_the_bot_heard_the_unrealised_and_the_total_say_so() -> None:
    facts = bot_facts(_running(replace(_HELD, pnl=_pnl(None))), NOW)

    assert facts.unrealised == "no price yet"
    assert facts.total_pnl == "no price yet"
    assert facts.hodl == "—"


def test_a_flat_bot_shows_no_unrealised_and_a_total_equal_to_what_it_realised() -> None:
    flat = replace(
        _PRICED,
        inventory=Decimal(0),
        average_cost=None,
        pnl=_pnl("65000", inventory="0"),
    )

    facts = bot_facts(_running(flat), NOW)

    assert facts.unrealised == "—"
    assert facts.total_pnl == "20.00"


def test_fees_that_could_not_be_priced_make_the_total_say_it_is_short() -> None:
    short = replace(_PRICED, pnl=replace(_PRICED.pnl, unpriced_fees=2))

    assert "2 fees could not be priced" in bot_facts(_running(short), NOW).total_pnl


def test_the_state_carries_its_reason_and_capital_comes_from_the_kinds_key() -> None:
    facts = bot_facts(_running(), NOW)

    assert facts.state == "Halted — trading turned off"
    assert facts.capital == "1000"
    assert facts.grid_profit == "12.50"


def test_running_time_counts_from_the_run_start_and_stops_at_rest() -> None:
    """A duration the formatter writes (`EPIC-033N`), not text written here."""
    elapsed = timedelta(days=1, hours=2, minutes=5)
    bot = replace(_running(), run_started_at=NOW - elapsed)

    assert bot_facts(bot, NOW).running_time == elapsed
    stopped = replace(bot, state=BotLifecycleState.STOPPED)
    assert bot_facts(stopped, NOW).running_time is None


def test_a_run_started_in_the_future_has_run_for_nothing() -> None:
    """A clock behind the stored start never reads as a negative time."""
    bot = replace(_running(), run_started_at=NOW + timedelta(minutes=3))

    assert bot_facts(bot, NOW).running_time == timedelta(0)


def test_base_earlier_runs_left_is_named_with_its_cost_and_otherwise_shows_nothing() -> (
    None
):
    """`BUG-196` — the figure a new run does not trade is not left unsaid."""
    none = bot_facts(_running(), NOW).earlier_runs
    left = bot_facts(
        _running(
            replace(
                _HELD,
                earlier_runs_base=Decimal("0.0083"),
                earlier_runs_cost=Decimal("20.5"),
            )
        ),
        NOW,
    ).earlier_runs

    assert none == NO_VALUE
    assert "0.0083" in left
    assert "not traded by this run" in left
