"""`EPIC-029B` — handler for `StopBotCommand`.

`EPIC-029E`: checked against the lifecycle table here, carried out by the
bot's executor (`BotCommandGate`, ADR D9). The executor moves the bot to
STOPPING; STOPPED comes only from `stop_confirmed`, after a read shows zero
open orders carrying the bot's tag (ADR §3.1).

`EPIC-039H` (decision O8): a bot on a position venue is never stopped with its position kept.
The choice is refused in words, because a leveraged position left standing has no stop on the
exchange yet (`EPIC-039L` lets a standing stop make "keep" an honest answer).

`BUG-274`: a person's Stop on a closed order session opens it first (as Resume and the headless
`bot stop` do, through `order_session_refusal`, passing the venue's position claims as they do,
`BUG-250`), or is refused in the session's words; before, the bot went to STOPPING and waited for
a session nobody opened. A Stop that carries no answer of a person's opens nothing.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_position_claims import (
    venue_position_claims,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_gate import (
    BotCommandGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.order_session_opening import (
    order_session_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot.command import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    keep_on_stop_closed_reason,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)


class StopBotCommandHandler(ICommandHandler[StopBotCommand, BotCommandResult]):
    """Refuses `stop` where the table does not declare it; otherwise queues it."""

    def __init__(
        self, store: IBotStore, runner: IBotRunner, ports: IVenueTradingPorts
    ) -> None:
        self._store = store
        self._gate = BotCommandGate(store)
        self._lookup = BotLookup(store)
        self._runner = runner
        self._ports = ports

    def execute(self, command: StopBotCommand) -> BotCommandResult:
        refused = self._gate.refusal(command.bot_id, BotLifecycleEvent.STOP)
        if refused is None:
            refused = self._keep_refusal(command)
        if refused is None and command.real_money_confirmed:
            refused = self._session_refusal(command)
        if refused is not None:
            return refused
        return self._gate.run(
            command.bot_id,
            BotLifecycleEvent.STOP,
            lambda bot_id: self._runner.stop(bot_id, command.base),
        )

    def _session_refusal(self, command: StopBotCommand) -> BotCommandResult | None:
        """Open the venue's order session if it is closed; the refusal in its words otherwise."""
        found = self._lookup.find(command.bot_id)
        if isinstance(found, BotCommandResult):
            return found
        venue = found.bot.definition.venue
        if venue_profile_of(venue) is None:
            return None  # the executor's stop answers it, in its words
        session = self._ports.get(venue).trading_session
        if session.snapshot().enabled:
            return None
        return order_session_refusal(
            session,
            command.bot_id,
            venue_position_claims(
                venue, (stored.bot for stored in self._store.load_all().bots)
            ),
        )

    def _keep_refusal(self, command: StopBotCommand) -> BotCommandResult | None:
        if command.base is not ExposureHandling.KEEP:
            return None
        found = self._lookup.find(command.bot_id)
        if isinstance(found, BotCommandResult):
            return found
        profile = venue_profile_of(found.bot.definition.venue)
        if profile is None or keep_on_stop_closed_reason(profile) is None:
            return None
        return BotCommandResult.refused(
            BotRefusal.EXPOSURE_MUST_CLOSE,
            f"{profile.title_word} positions are not kept when a bot stops: this app places "
            "no stop on the exchange yet, and a leveraged position with no stop can be "
            "liquidated. Stop and close the position.",
            command.bot_id,
        )
