"""`EPIC-045C` - the host's "the plan no longer names this bot", answered by the applied-plan record.

Offline, `bot apply` rewrites `state/bot_plan.json` from the plan, so a bot the plan does not name has no row
afterwards and `run --start-planned` stops acting on it. Beside a running host the record is changed a row at a
time (`wish_ledger.py`), and this is the row removal. It touches the record and nothing else: the bot is not
stopped, edited or deleted. A bot with no recorded wish is answered, not refused: the operator wanted it gone
from the record and it is.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.wish_ledger import (
    forget_wish,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    UnplanBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)


class UnplanBotForHostCommandHandler(
    ICommandHandler[UnplanBotForHostCommand, BotCommandResult]
):
    def __init__(self, plans: IAppliedPlanStore, lock: BotCommandLock) -> None:
        self._plans = plans
        self._lock = lock

    def execute(self, command: UnplanBotForHostCommand) -> BotCommandResult:
        with self._lock.held():
            had = forget_wish(self._plans, command.bot_id)
        words = (
            f"bot {command.bot_id}: its wish was removed from the applied plan, so "
            "`run --start-planned` no longer acts on it; the bot itself is untouched"
            if had
            else f"bot {command.bot_id} had no wish in the applied plan; nothing to remove"
        )
        return BotCommandResult(accepted=True, bot_id=command.bot_id, message=words)
