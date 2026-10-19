"""`BUG-227` - a read-only copy of the Bots tab follows what the writing copy saves.

@details Another copy holds the data root and trades; this one only reads (`EPIC-035H`). The writer
announces its saves on its own bus (`BotChangedEvent`), which this process never hears, so the tab
re-reads the bots' files on its own clock: a cycle the writer books reaches the table without a
restart. The writer is not re-read on the clock: it hears its own saves.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)

from .bots_screen_fixtures import BotsScreen, stored

S = BotLifecycleState
TOTAL_PNL_COLUMN = 5


def _with_profit(bot: StoredBot, profit: str) -> StoredBot:
    """The bot as the writer saves it after booking `profit`: nothing held, so the total is
    the profit and needs no price."""
    runtime = replace(
        GridRuntime(()),
        realised_profit=Decimal(profit),
        realised_total=Decimal(profit),
        completed_cycles=1,
    )
    return StoredBot(bot.bot, encode_runtime(runtime))


def _total_pnl_cell(screen: BotsScreen) -> object:
    return screen.view.bots.index(0, TOTAL_PNL_COLUMN).data()


def _clock_ticks(screen: BotsScreen) -> None:
    screen.presenter._clock.timeout.emit()
    screen.settle()


def test_a_read_only_copy_shows_a_cycle_the_writer_booked_after_it_opened(
    open_bots_screen, tmp_path: Path
) -> None:
    writer = JsonBotStore(tmp_path)
    running = stored("a00001", S.RUNNING)
    writer.save(_with_profit(running, "1.25"))
    screen = open_bots_screen(instance=InstanceAccess.declined("another copy writes"))
    screen.settle()
    assert "1.25" in str(_total_pnl_cell(screen))

    writer.save(_with_profit(running, "7.50"))
    _clock_ticks(screen)

    assert "7.50" in str(_total_pnl_cell(screen))


def test_the_writing_copy_does_not_re_read_on_its_clock(
    open_bots_screen, tmp_path: Path
) -> None:
    screen = open_bots_screen([_with_profit(stored("a00001", S.RUNNING), "1.25")])
    screen.settle()
    JsonBotStore(tmp_path).save(_with_profit(stored("a00001", S.RUNNING), "7.50"))

    _clock_ticks(screen)

    assert "1.25" in str(_total_pnl_cell(screen))
