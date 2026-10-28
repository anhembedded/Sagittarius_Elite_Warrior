"""`EPIC-047E` — the dispatcher behind the VPS tab: the Bots screen's own doors, on the other side of the link.

@details The Bots screen reaches the application only through `ICommandDispatcher` and the event bus
(`architecture-rule.md` §3.1, `EPIC-048`). This is a second dispatcher: a **query** is answered from what the
host last published (`RemoteQueries`, even when the link is down, with the data's age beside it); a **command**
becomes the host's request (`remote_requests`) and goes through `IHostControl` to the host's own gate and
audit; the pure assessment (`AssessBotQuery`) runs here, where the screen runs, on the local dispatcher —
it reads nothing.

@par What it refuses, and how
  · a command while the link is down is not sent: a `BotCommandResult` says so in words and nothing reaches the
    host (the screen is read-only while disconnected, `EPIC-047` O5/D5);
  · a query or command the VPS tab does not offer (the Backtest workbench, the plan file) raises
    `NotOfferedInVpsTabError`, which the screen already shows as a failure with its words.

Capability: Answer the Bots screen's queries and carry its commands from a remote host's published facts and control door, so a second tab shows another host's bots with the same classes
    Also: vps tab, remote bots, remote dispatcher, second backend for the bots screen, host facts, bridge commands, disconnected data as of, not published by the host
    Use: RemoteCommandDispatcher, RemoteQueries
    User: tests/unit/shell/vps_link/dispatcher_world.py
    Status: stable

@par A command is never sent twice
This class sends once. A command lost in flight comes back from the link as a `NO_ANSWER` reply, shown as such;
the host's audit knows whether it ran (`EPIC-047E`'s reconcile reads it by the same request id).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlRequest,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_host_control import IHostControl
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.remote_host.remote_queries import (
    QueryNotServedError,
    RemoteQueries,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.remote_host.remote_requests import (
    NothingToSend,
    proposal_in,
    request_of,
    result_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.assess_bot import (
    AssessBotQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume import (
    ConfirmBotResumeCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_world import HostWorld
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_host_world import IHostWorld

logger = logging.getLogger("App.VpsTab")

#: How long a command waits for the host's recorded answer; under the bridge's own 30 s ceiling, over the 10 s
#: a resume proposal takes (`PROPOSAL_REPLY_WAIT_S`).
COMMAND_WAIT_S: Final = 15.0
DISCONNECTED_WORDS = (
    "Not connected to the host: the command was not sent. The tab reconnects by itself; "
    "try again when it shows connected."
)


class RemoteCommandDispatcher(ICommandDispatcher):
    def __init__(
        self,
        world: IHostWorld,
        control: IHostControl,
        queries: RemoteQueries,
        local: ICommandDispatcher,
    ) -> None:
        self._world = world
        self._control = control
        self._queries = queries
        self._local = local
        self._proposals: dict[str, str] = {}

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        if handler_class is AssessBotQuery:
            return self._local.dispatch(handler_class, input_dto)
        message = input_dto if input_dto is not None else handler_class()
        current = self._world.current()
        try:
            return self._queries.answer(message, current)
        except QueryNotServedError:
            pass
        return self._command(message, current)

    def _command(self, message: object, current: HostWorld) -> BotCommandResult:
        if isinstance(message, ConfirmBotResumeCommand) and message.proposal is None:
            # The screen confirms the proposal it was shown; the host's confirmation names it by fingerprint.
            message = replace(message, proposal=self._proposals.get(message.bot_id))
        translated = request_of(message, {bot.bot_id: bot for bot in current.bots})
        if isinstance(translated, BotCommandResult):
            return translated
        if isinstance(translated, NothingToSend):
            return translated.result
        if not current.connected:
            logger.info(
                "[vps-command] %s on %s not sent: the link is down",
                translated.action.value,
                translated.bot_id,
            )
            return BotCommandResult.refused(
                BotRefusal.READ_ONLY_INSTANCE, DISCONNECTED_WORDS, translated.bot_id
            )
        return self._send(translated)

    def _send(self, request: HostControlRequest) -> BotCommandResult:
        reply = self._control.send(request, COMMAND_WAIT_S)
        logger.info(
            "[vps-command] %s on %s: host says %s",
            request.action.value,
            request.bot_id,
            reply.status.value,
        )
        result = result_of(request, reply)
        if request.action is HostControlAction.RESUME and result.accepted:
            self._remember_proposal(request.bot_id, result.message)
        return result

    def _remember_proposal(self, bot_id: str, words: str) -> None:
        fingerprint = proposal_in(words)
        if fingerprint is None:
            self._proposals.pop(bot_id, None)
        else:
            self._proposals[bot_id] = fingerprint
