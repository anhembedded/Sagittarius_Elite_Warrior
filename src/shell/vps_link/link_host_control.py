"""`EPIC-047E` — the host's control door, reached over the link.

@details `IHostControl` is the operator's side of control: a request in, the host's recorded answer out. This one
carries it as the bridge's `command` call (`support/wire/bridge/bridge_commands.py`): one fresh request id per
command, the id the host's audit remembers. It never sends a command twice — a cut link ends the wait as
`NO_ANSWER` with the id in the words and in `unanswered`, and whether the host ran it is the audit's to say
(`EPIC-047E`'s reconcile asks again under the same id).

@par What each ending is
  · the host answered — its reply, verbatim;
  · no link — `NOT_RUNNING`, nothing was written;
  · the bridge refused the call (too many waiting, a duplicate id) — `REJECTED`, with its words;
  · the link was cut or timed out with the command waiting — `NO_ANSWER`.
"""

from __future__ import annotations

import logging
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_host_control import IHostControl
from Sagittarius_Elite_Warrior.src.shell.vps_link.link_host_world import LinkHostWorld
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    REPLY_ROOT,
    REQUEST_ROOT,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    CallFailedError,
    CallTimedOutError,
    CommandInFlightLostError,
    LinkLostError,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import WireDecodeError
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots

logger = logging.getLogger("App.VpsTab")

_NOT_CONNECTED = "Not connected to the host: nothing was sent."
_UNREADABLE = "The host's reply could not be read by this build; see its audit."


@dataclass(frozen=True, slots=True)
class UnansweredCommand:
    """A command whose outcome is not known: the link ended with it waiting."""

    request_id: str
    request: HostControlRequest


class LinkHostControl(IHostControl):
    def __init__(
        self,
        world: LinkHostWorld,
        roots: WireRoots,
        new_request_id: Callable[[], str] = lambda: secrets.token_hex(16),
    ) -> None:
        self._world = world
        self._roots = roots
        self._new_request_id = new_request_id
        self._lock = threading.Lock()
        self._unanswered: list[UnansweredCommand] = []

    @property
    def unanswered(self) -> tuple[UnansweredCommand, ...]:
        """The commands whose outcome the desktop does not know, oldest first."""
        with self._lock:
            return tuple(self._unanswered)

    def send(self, request: HostControlRequest, wait_s: float) -> HostControlReply:
        link = self._world.live_link()
        if link is None:
            return HostControlReply(HostControlStatus.NOT_RUNNING, _NOT_CONNECTED)
        request_id = self._new_request_id()
        try:
            data = link.command(
                request_id, self._roots.encode(REQUEST_ROOT, request), wait_s
            )
        except CommandInFlightLostError:
            return self._lost(request_id, request, "the link was cut")
        except CallTimedOutError:
            return self._lost(request_id, request, "the host did not answer in time")
        except LinkLostError:
            return HostControlReply(HostControlStatus.NOT_RUNNING, _NOT_CONNECTED)
        except CallFailedError as refused:
            return HostControlReply(
                HostControlStatus.REJECTED,
                f"The bridge refused the command: {refused}",
                request_id,
            )
        return self._reply_of(data, request_id)

    def _reply_of(self, data: dict[str, object], request_id: str) -> HostControlReply:
        try:
            decoded = self._roots.decode(data.get("reply"))
            if self._roots.schema_of(data.get("reply")) != REPLY_ROOT:
                raise WireDecodeError(f"a reply carries {REPLY_ROOT}")
        except WireDecodeError:
            return HostControlReply(
                HostControlStatus.NO_ANSWER, _UNREADABLE, request_id
            )
        if not isinstance(decoded, HostControlReply):
            return HostControlReply(
                HostControlStatus.NO_ANSWER, _UNREADABLE, request_id
            )
        return decoded

    def _lost(
        self, request_id: str, request: HostControlRequest, why: str
    ) -> HostControlReply:
        with self._lock:
            self._unanswered.append(UnansweredCommand(request_id, request))
        logger.warning(
            "[vps-command] %s on %s (request %s): %s with the command waiting; it was not sent again",
            request.action.value,
            request.bot_id,
            request_id,
            why,
        )
        return HostControlReply(
            HostControlStatus.NO_ANSWER,
            f"The outcome is not known: {why} while the command waited. It was not sent again; "
            f"the host's audit says whether it ran (request {request_id}).",
            request_id,
        )
