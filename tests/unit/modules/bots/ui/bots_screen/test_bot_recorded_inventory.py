"""`BOT-174` — what the screen judges a resume with is the run's record, as stored."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_progress_reader import (
    bot_progress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_detail import (
    _recorded_inventory,
)

from .bots_screen_fixtures import stored


def test_the_cost_is_the_runtimes_own_not_inventory_times_an_average() -> None:
    """3 × (10 / 3) is not 10 in Decimal: the last digit would differ."""
    runtime = GridRuntime((), inventory=Decimal(3), cost=Decimal(10))
    halted = stored("a00001", S.HALTED)
    record = StoredBot(halted.bot, encode_runtime(runtime))
    snapshot = BotSnapshot.of(record.bot, bot_progress(record))

    held = _recorded_inventory(snapshot)

    assert (held.quantity, held.cost) == (Decimal(3), Decimal(10))
    assert snapshot.progress is not None
    assert snapshot.progress.inventory * snapshot.progress.average_cost != Decimal(10)  # type: ignore[operator]


def test_a_bot_with_no_run_holds_nothing() -> None:
    snapshot = BotSnapshot.of(stored("a00001", S.HALTED).bot, None)

    held = _recorded_inventory(snapshot)

    assert (held.quantity, held.cost) == (Decimal(0), Decimal(0))
