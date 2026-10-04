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
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    bot_facts,
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


def test_unrealised_pnl_is_what_the_held_base_gained_at_the_latest_price() -> None:
    facts = bot_facts(_running(), Decimal(65000), NOW)

    assert facts.unrealised == "+10 at 65000"
    assert bot_facts(_running(), Decimal(63000), NOW).unrealised == "-10 at 63000"


def test_without_a_price_unrealised_pnl_says_so_and_without_base_shows_nothing() -> (
    None
):
    assert bot_facts(_running(), None, NOW).unrealised == "no price yet"
    flat = replace(_HELD, inventory=Decimal(0), average_cost=None)
    assert bot_facts(_running(flat), Decimal(65000), NOW).unrealised == "—"


def test_the_state_carries_its_reason_and_capital_comes_from_the_kinds_key() -> None:
    facts = bot_facts(_running(), None, NOW)

    assert facts.state == "Halted — trading turned off"
    assert facts.capital == "1000"
    assert facts.grid_profit == "+12.5"


def test_running_time_counts_from_the_run_start_and_stops_at_rest() -> None:
    bot = replace(
        _running(), run_started_at=NOW - timedelta(days=1, hours=2, minutes=5)
    )

    assert bot_facts(bot, None, NOW).running_time == "1d 02h 05m"
    short = replace(bot, run_started_at=NOW - timedelta(minutes=7))
    assert bot_facts(short, None, NOW).running_time == "0h 07m"
    stopped = replace(bot, state=BotLifecycleState.STOPPED)
    assert bot_facts(stopped, None, NOW).running_time == "—"
