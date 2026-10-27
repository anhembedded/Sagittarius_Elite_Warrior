"""`EPIC-038J` - a person's `bot stop` on the running host: open the order session if it is closed, then Stop.

The screen's Stop does not open the venue's order session, so after an Emergency Stop or a restart
(both leave it closed) a Stop is accepted and waits in STOPPING for a session nobody opens: the
headless host has no switch to flip. The owner's answer "B" (2026-10-17) is that `bot stop` opens it
itself, as Resume and Start do, through the one place that does (`order_session_refusal_for_stop`).

Order, so that nothing is opened for a stop that would be refused:
  1. the bot exists and the lifecycle table allows `stop` from its state;
  2. a position venue is refused unless the operator typed `--close-position` (`BUG-224`): a kept
     position has no stop on the exchange (`EPIC-039H`), and the host's stop used to carry KEEP, so
     no Futures bot could be stopped. The refusal names the flag and says the command closes the
     position at market; with it the stop carries `ExposureHandling.CLOSE_AT_MARKET`, the choice
     the screen's "Close the position at market" makes;
  3. a closed session on a **mainnet** venue is opened only when the operator typed the venue
     (decision O8); an open session needs no answer, because Stop places no order;
  4. the session is opened (`ensure_ready`), or the refusal in its words is the answer;
  5. the Stop is `StopBotForHostCommand` - the stop the host's shutdown policy uses (it keeps the
     base unless told to close), which dispatches the screen's `StopBotCommand`. A Spot bot keeps its
     base without the flag; with it, it is sold, as the screen's close does.

Opening the session reconciles every bot on that venue, exactly as Start, Resume and
`run --resume-recovering` do: a RECOVERING bot returns to the state it had before the restart. The
refusal that asks for the typed mainnet venue names those other bots, so the typed venue is an
informed consent; the runbook says so. The shutdown policy keeps using
`StopBotForHostCommand` and still opens nothing.
"""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
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
    order_session_refusal_for_stop,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    StopBotForHostCommand,
    StopBotForOperatorCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    keep_on_stop_closed_reason,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
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
        self._store = store
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
        if profile is None:
            return self._stop(
                command.bot_id, ExposureHandling.KEEP
            )  # the screen's Stop answers it, in its words
        if (
            keep_on_stop_closed_reason(profile) is not None
            and not command.close_position
        ):
            return BotCommandResult.refused(
                BotRefusal.EXPOSURE_MUST_CLOSE,
                f"{profile.title_word} positions are not kept when a bot stops, so stopping bot "
                f"{command.bot_id} closes its position at market. Nothing was changed; to stop "
                "it and close the position, add --close-position.",
                command.bot_id,
            )
        exposure = (
            ExposureHandling.CLOSE_AT_MARKET
            if command.close_position
            else ExposureHandling.KEEP
        )
        session = self._ports.get(venue).trading_session
        if not session.snapshot().enabled:
            if venue.is_mainnet and command.confirmed_venue != venue.value:
                return BotCommandResult.refused(
                    BotRefusal.REAL_MONEY_NOT_CONFIRMED,
                    f"The order session of {venue.display_name} is closed, and stopping bot "
                    f"{command.bot_id} needs it open (an Emergency Stop or a restart closes it). "
                    f"Opening it uses real money's session{self._others_waiting(command.bot_id, found)}: "
                    f"type --confirm-venue {venue.value}.",
                    command.bot_id,
                )
            # `BUG-250`: the position a host stop left under the bot's stop is its own.
            opened = order_session_refusal_for_stop(
                session,
                command.bot_id,
                venue_position_claims(
                    venue, (stored.bot for stored in self._store.load_all().bots)
                ),
            )
            if opened is not None:
                return opened
        return self._stop(command.bot_id, exposure)

    def _others_waiting(self, bot_id: str, stopping: StoredBot) -> str:
        """What opening the session does to the venue's other bots, in words (`BOT-183`): nothing.
        The opening is announced as opened for the stopped bot, so a RECOVERING one keeps waiting
        for its own resume; the words say so, so the operator who typed the venue is not left
        thinking the stop resumed it."""
        venue = stopping.bot.definition.venue
        others = sorted(
            stored.bot.bot_id.value
            for stored in self._store.load_all().bots
            if stored.bot.definition.venue is venue
            and stored.bot.state is BotLifecycleState.RECOVERING
            and stored.bot.bot_id.value != bot_id
        )
        if not others:
            return ""
        return (
            f", and the other RECOVERING bot(s) on {venue.display_name} "
            f"({', '.join(others)}) keep waiting for their own resume"
        )

    def _stop(self, bot_id: str, exposure: ExposureHandling) -> BotCommandResult:
        return cast(
            BotCommandResult,
            self._dispatcher.dispatch(
                StopBotForHostCommand, StopBotForHostCommand(bot_id, exposure)
            ),
        )
