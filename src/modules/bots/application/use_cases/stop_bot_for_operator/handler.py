"""`EPIC-038J` - a person's `bot stop` on the running host: open the order session if it is closed, then Stop.

The screen's Stop does not open the venue's order session, so after an Emergency Stop or a restart
(both leave it closed) a Stop is accepted and waits in STOPPING for a session nobody opens: the
headless host has no switch to flip. The owner's answer "B" (2026-10-17) is that `bot stop` opens it
itself, as Resume and Start do, through the one place that does (`order_session_refusal`).

Order, so that nothing is opened for a stop that would be refused:
  1. the bot exists and the lifecycle table allows `stop` from its state;
  2. a position venue is refused as the screen's Stop refuses it (a kept position has no stop on
     the exchange, `EPIC-039H`);
  3. a closed session on a **mainnet** venue is opened only when the operator typed the venue
     (decision O8); an open session needs no answer, because Stop places no order;
  4. the session is opened (`ensure_ready`), or the refusal in its words is the answer;
  5. the Stop is `StopBotForHostCommand` - the same keep-the-base stop the host's shutdown policy
     uses, which dispatches the screen's `StopBotCommand`.

Opening the session reconciles every bot on that venue, exactly as Start, Resume and
`run --resume-recovering` do; the runbook says so. The shutdown policy keeps using
`StopBotForHostCommand` and still opens nothing.
"""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_gate import (
    BotCommandGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.order_session_opening import (
    order_session_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    StopBotForHostCommand,
    StopBotForOperatorCommand,
)
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


class StopBotForOperatorCommandHandler(
    ICommandHandler[StopBotForOperatorCommand, BotCommandResult]
):
    def __init__(
        self,
        store: IBotStore,
        ports: IVenueTradingPorts,
        dispatcher: ICommandDispatcher,
    ) -> None:
        self._gate = BotCommandGate(store)
        self._lookup = BotLookup(store)
        self._ports = ports
        self._dispatcher = dispatcher

    def execute(self, command: StopBotForOperatorCommand) -> BotCommandResult:
        refusal = self._gate.refusal(command.bot_id, BotLifecycleEvent.STOP)
        if refusal is not None:
            return refusal
        found = self._lookup.find(command.bot_id)
        if isinstance(found, BotCommandResult):
            return found
        venue = found.bot.definition.venue
        profile = venue_profile_of(venue)
        if profile is None or keep_on_stop_closed_reason(profile) is not None:
            return self._stop(
                command.bot_id
            )  # the screen's Stop refuses it, in its words
        session = self._ports.get(venue).trading_session
        if not session.snapshot().enabled:
            if venue.is_mainnet and command.confirmed_venue != venue.value:
                return BotCommandResult.refused(
                    BotRefusal.REAL_MONEY_NOT_CONFIRMED,
                    f"The order session of {venue.display_name} is closed, and stopping bot "
                    f"{command.bot_id} needs it open (an Emergency Stop or a restart closes it). "
                    f"Opening it uses real money's session: type --confirm-venue {venue.value}.",
                    command.bot_id,
                )
            opened = order_session_refusal(session, command.bot_id)
            if opened is not None:
                return opened
        return self._stop(command.bot_id)

    def _stop(self, bot_id: str) -> BotCommandResult:
        return cast(
            BotCommandResult,
            self._dispatcher.dispatch(
                StopBotForHostCommand, StopBotForHostCommand(bot_id)
            ),
        )
