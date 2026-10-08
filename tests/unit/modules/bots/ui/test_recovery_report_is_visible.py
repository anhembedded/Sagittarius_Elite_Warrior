"""`EPIC-035C` (H6) — the boot report is a line the user reads, not a log record.

The report is stored on the bot as its reason (the one place the Bots screen
reads a bot's "why"), then reaches the detail panel through `bot_progress` and
`bot_facts`. The whole path is walked with the real report text.
"""

from __future__ import annotations

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
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.recovery_report import (
    RecoveryReport,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    bot_facts,
)

from .bots_screen.bots_screen_fixtures import NOW, stored


def test_the_recovery_report_is_in_the_bots_facts() -> None:
    report = RecoveryReport(resting=3, filled_while_closed=1, missing=0, foreign=2)
    bot = stored("a00001", BotLifecycleState.RECOVERING).bot
    runtime = GridRuntime(()).with_reason(GridReason.RECOVERY_READ, report.words())
    progress = bot_progress(StoredBot(bot, encode_runtime(runtime)))

    facts = bot_facts(BotSnapshot.of(bot, progress), None, NOW)

    assert facts.state == f"Recovering — {report.words()}"
    assert "3 saved order(s) rest" in facts.state
    assert "1 filled while the app was closed" in facts.state
    assert "2 not saved by the bot" in facts.state


def test_a_stopping_bot_shows_why_it_waits_and_what_is_still_open() -> None:
    bot = stored("a00002", BotLifecycleState.STOPPING).bot
    detail = "waiting: 4 order(s) carrying the tag are still open; retries are used up"
    runtime = GridRuntime(()).with_reason(GridReason.USER_STOP, detail)
    progress = bot_progress(StoredBot(bot, encode_runtime(runtime)))

    facts = bot_facts(BotSnapshot.of(bot, progress), None, NOW)

    assert facts.state == f"Stopping — {detail}"
