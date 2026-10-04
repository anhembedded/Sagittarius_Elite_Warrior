"""`EPIC-029B` — handler for `StartBotCommand`.

Start's preconditions are checked **before** the `start` transition, so a
refusal leaves the bot in DRAFT or STOPPED with nothing to clean up (ADR §3.1).
This task checks the one precondition the bots module can answer alone:

  · **one running bot (ADR D20).** During the fast track only one bot may hold
    the exchange. "Running" here means every state but DRAFT and STOPPED: a
    STARTING, PAUSED, HALTED, RECOVERING, STOPPING or ERROR bot may still own
    orders, a lease or a budget, so a second bot starting beside it would share
    the account it is reconciling. A file the store refused counts as active
    too: its state is unknown, so it is treated as the worst case.

`EPIC-029E` adds the rest through the runner (`IBotRunner.start`): the venue
enabled, no REFUSED verdict, the lease and the budget, then STARTING and the
queued start. **The D20 check and the start are one step** (the PR #318
review): both run under `BotCommandLock`, so two starts dispatched at once
cannot both find no other bot active.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot.command import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RUN_STARTING_STATES,
)


class StartBotCommandHandler(ICommandHandler[StartBotCommand, BotCommandResult]):
    """Refuses while another bot is active; otherwise moves the bot to STARTING."""

    def __init__(
        self, store: IBotStore, runner: IBotRunner, lock: BotCommandLock
    ) -> None:
        self._store = store
        self._runner = runner
        self._lock = lock

    def execute(self, command: StartBotCommand) -> BotCommandResult:
        with self._lock.held():
            active = self._other_active_bot(command.bot_id)
            if active is not None:
                return BotCommandResult.refused(
                    BotRefusal.ONE_RUNNING_BOT_DURING_FAST_TRACK,
                    f"Bot {active} is still active; stop it before starting another",
                    command.bot_id,
                )
            return self._runner.start(command.bot_id)

    def _other_active_bot(self, bot_id: str) -> str | None:
        reading = self._store.load_all()
        for stored in reading.bots:
            other = stored.bot
            if other.bot_id.value != bot_id and other.state not in RUN_STARTING_STATES:
                return other.bot_id.value
        for refused in reading.refused:
            if not refused.name.startswith(f"{bot_id}."):
                return refused.name
        return None
