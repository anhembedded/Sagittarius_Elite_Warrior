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
This class sends once, and holds a bot to one command at a time (`_begin`). A command lost in flight comes back from the link as a `NO_ANSWER` reply, shown as such;
the host's audit knows whether it ran (`EPIC-047E`'s reconcile reads it by the same request id).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, replace
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
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_world import HostWorld
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_host_world import IHostWorld
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_unanswered_commands import (
    IUnansweredCommands,
)

logger = logging.getLogger("App.VpsTab")

#: How long a command waits for the host's recorded answer; under the bridge's own 30 s ceiling, over the 10 s
#: a resume proposal takes (`PROPOSAL_REPLY_WAIT_S`).
COMMAND_WAIT_S: Final = 15.0


#: The verbs that only reduce what a bot holds or places. They pass the two blocks below (an unknown outcome and a
#: command in flight): applied twice they do the same as once, and the one control that lowers exposure is never
#: the one withheld. Every other verb is harmful when applied twice, or cannot be taken back.
REDUCES_EXPOSURE: Final = frozenset({HostControlAction.STOP, HostControlAction.PAUSE})
IN_FLIGHT_WORDS = "A command on this bot is still waiting for the host's answer: wait for it before sending another."


def unknown_outcome_words(request_ids: tuple[str, ...]) -> str:
    return (
        "An earlier command on this bot was lost with the link and its outcome is not known "
        f"(request {request_ids[0]}): check the host's audit before sending another, "
        "or it may be applied twice."
    )


def _refusal(words: str, subject: str) -> BotCommandResult:
    """A refusal made here, in words and without a code: the host was not asked."""
    return BotCommandResult(accepted=False, bot_id=subject, refusal=None, message=words)


DISCONNECTED_WORDS = (
    "Not connected to the host: the command was not sent. The tab reconnects by itself; "
    "try again when it shows connected."
)


@dataclass(frozen=True, slots=True)
class RemoteHostPorts:
    """What the dispatcher reaches the host through."""

    world: IHostWorld
    control: IHostControl
    #: The commands whose outcome is not known; a new one on the same bot is refused (see `_command`).
    unanswered: IUnansweredCommands


class RemoteCommandDispatcher(ICommandDispatcher):
    def __init__(
        self,
        ports: RemoteHostPorts,
        queries: RemoteQueries,
        local: ICommandDispatcher,
    ) -> None:
        self._world = ports.world
        self._control = ports.control
        self._unanswered = ports.unanswered
        self._queries = queries
        self._local = local
        self._proposals: dict[str, str] = {}
        self._lock = threading.Lock()
        self._in_flight: set[str] = set()

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
            return _refusal(DISCONNECTED_WORDS, translated.bot_id)
        if translated.action in REDUCES_EXPOSURE:
            return self._send(translated)
        pending = self._unanswered.request_ids_for(translated.bot_id)
        if pending:
            return _refusal(unknown_outcome_words(pending), translated.bot_id)
        if not self._begin(translated.bot_id):
            return _refusal(IN_FLIGHT_WORDS, translated.bot_id)
        try:
            return self._send(translated)
        finally:
            self._end(translated.bot_id)

    def _begin(self, subject: str) -> bool:
        """Claims the subject for one command; `False` when another waits on the host. The screen's own
        action tracker serialises its buttons, but the guarantee "never applied twice" does not rest on it."""
        with self._lock:
            if subject in self._in_flight:
                return False
            self._in_flight.add(subject)
            return True

    def _end(self, subject: str) -> None:
        with self._lock:
            self._in_flight.discard(subject)

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
