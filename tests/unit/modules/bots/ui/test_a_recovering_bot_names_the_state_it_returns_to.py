"""`BUG-206` — the screen says where a RECOVERING bot goes, and that a restored PAUSED bot waits.

@details A bot the owner paused comes back from RECOVERING to PAUSED (`BUG-204`), so
its one Resume only reconciles it. The state line promised "continue" and the second
press was a surprise; the line now names the state the reconcile returns to (the
bot's `recovering_from`, carried on the snapshot) and, after the return, the bot's
own reason says it stays paused and needs Resume.
"""

from __future__ import annotations

from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.recovery.grid_reconciler import (
    RESTORED_PAUSED_DETAIL,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_progress_reader import (
    bot_progress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import BotLifecycle
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    RECOVERING_FROM_PAUSED_WAITS_FOR_RESUME,
    RECOVERING_WAITS_FOR_RESUME,
    bot_facts,
)

from .bots_screen.bots_screen_fixtures import NOW, stored

S = BotLifecycleState


def _recovering(prior: S | None) -> BotSnapshot:
    bot = stored("a00006", S.RECOVERING).bot
    bot = replace(bot, lifecycle=BotLifecycle(S.RECOVERING, NOW, prior))
    return BotSnapshot.of(bot)


def test_a_bot_paused_before_the_restart_says_it_returns_to_paused() -> None:
    state = bot_facts(_recovering(S.PAUSED), NOW).state

    assert state.startswith(f"Recovering — {RECOVERING_FROM_PAUSED_WAITS_FOR_RESUME}")
    assert "was Paused before the restart" in state
    assert "returns it to Paused" in state
    assert "press Resume again to run" in state


def test_a_bot_running_before_the_restart_says_resume_continues_it() -> None:
    state = bot_facts(_recovering(S.RUNNING), NOW).state

    assert state.startswith(f"Recovering — {RECOVERING_WAITS_FOR_RESUME}")
    assert "Paused" not in state


def test_the_snapshot_carries_the_prior_state_as_data() -> None:
    assert _recovering(S.PAUSED).recovering_from is S.PAUSED
    assert BotSnapshot.of(stored("a00007", S.RUNNING).bot).recovering_from is None


def test_a_bot_restored_to_paused_says_it_stays_paused_and_needs_resume() -> None:
    """After the reconcile returned the bot to PAUSED, the screen - not only the log -
    says so; this is what the owner reads where the dropped Resume used to be silent."""
    bot = replace(
        stored("a00008", S.PAUSED).bot, lifecycle=BotLifecycle(S.PAUSED, NOW, None)
    )
    runtime = GridRuntime(()).with_reason(
        GridReason.RESTORED_PAUSED, RESTORED_PAUSED_DETAIL
    )
    progress = bot_progress(StoredBot(bot, encode_runtime(runtime)))

    state = bot_facts(BotSnapshot.of(bot, progress), NOW).state

    assert state == f"Paused — {RESTORED_PAUSED_DETAIL}"
    assert "stays paused" in state
    assert "Press Resume to run" in state
