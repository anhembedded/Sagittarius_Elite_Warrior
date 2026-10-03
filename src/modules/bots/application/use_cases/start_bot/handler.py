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

The others — the venue enabled, no REFUSED verdict, the lease, the budget —
need trading's ports and the kind's terms, and arrive with the executor
(`EPIC-029E`), which also turns STARTING into orders.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_event_runner import (
    BotEventRunner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot.command import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RUN_STARTING_STATES,
    BotLifecycleEvent,
)


class StartBotCommandHandler(ICommandHandler[StartBotCommand, BotCommandResult]):
    """Refuses while another bot is active; otherwise moves the bot to STARTING."""

    def __init__(self, store: IBotStore, clock: IBotClock) -> None:
        self._store = store
        self._runner = BotEventRunner(store, clock)

    def execute(self, command: StartBotCommand) -> BotCommandResult:
        active = self._other_active_bot(command.bot_id)
        if active is not None:
            return BotCommandResult.refused(
                BotRefusal.ONE_RUNNING_BOT_DURING_FAST_TRACK,
                f"Bot {active} is still active; stop it before starting another",
                command.bot_id,
            )
        return self._runner.run(command.bot_id, BotLifecycleEvent.START)

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
