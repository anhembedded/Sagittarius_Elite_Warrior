"""`EPIC-047C` — the bridge's commands: decode one, send it through the host's door on a thread of its own, answer.

A command is the only call that waits (the host answers in about a second), so it runs on a
short-lived thread and the rest of the session, events and heartbeats included, does not stand
still. At most `MAX_PENDING_COMMANDS` wait at once. The bridge dedupes nothing: it is a new process
after a reconnect, so the desktop's request id is the key and the host's audit is the memory
(`ICommandDoor`).
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable
from typing import Final

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlRequest,
)
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    DEFAULT_COMMAND_WAIT_S,
    MAX_PENDING_COMMANDS,
    MESSAGE_LIMIT,
    REPLY_ROOT,
    REQUEST_ROOT,
    CallError,
    error_message,
    wait_of,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_command_door import (
    ICommandDoor,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import WireDecodeError
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots

logger = logging.getLogger("App.LinkBridge")

_REQUEST_ID: Final = re.compile(r"[0-9a-f]{32}")

type Send = Callable[[dict[str, object]], None]
type Spawn = Callable[[Callable[[], None]], None]


class BridgeCommands:
    def __init__(
        self, roots: WireRoots, door: ICommandDoor, spawn: Spawn, send: Send
    ) -> None:
        self._roots = roots
        self._door = door
        self._spawn = spawn
        self._send = send
        self._pending: dict[int, str] = {}
        self._lock = threading.Lock()
        self.served = 0

    def start(self, call_id: int, params: dict[str, object]) -> None:
        """Check the call and hand it to a thread; the result is sent when the host has answered.
        @raise CallError The call is malformed, or too many commands wait already."""
        request_id = params.get("request_id")
        if type(request_id) is not str or not _REQUEST_ID.fullmatch(request_id):
            raise CallError("bad_command", "request_id is 32 lowercase hex characters")
        wait_s = wait_of(params.get("wait_s", DEFAULT_COMMAND_WAIT_S))
        request = self._request_of(params.get("request"))
        with self._lock:
            if request_id in self._pending.values():
                # Two sends of one id at once would race on one command file (review round 1).
                raise CallError(
                    "duplicate",
                    "a command with this request_id is already waiting; wait for its result",
                )
            if len(self._pending) >= MAX_PENDING_COMMANDS:
                raise CallError(
                    "busy", f"{MAX_PENDING_COMMANDS} commands are waiting already"
                )
            self._pending[call_id] = request_id
        self._spawn(lambda: self._run(call_id, request_id, request, wait_s))

    def _request_of(self, message: object) -> HostControlRequest:
        try:
            request = self._roots.decode(message)
            if self._roots.schema_of(message) != REQUEST_ROOT:
                raise WireDecodeError(f"a command carries {REQUEST_ROOT}")
        except WireDecodeError as failure:
            raise CallError("bad_command", str(failure)[:MESSAGE_LIMIT]) from failure
        if not isinstance(request, HostControlRequest):
            raise CallError("bad_command", f"a command carries {REQUEST_ROOT}")
        return request

    def _run(
        self,
        call_id: int,
        request_id: str,
        request: HostControlRequest,
        wait_s: float,
    ) -> None:
        try:
            reply = self._door.send(request_id, request, wait_s)
            message = self._roots.encode(REPLY_ROOT, reply)
        except Exception:
            logger.exception(
                "[link-bridge] the control door failed for call %d", call_id
            )
            self._send(
                error_message(
                    call_id,
                    "door_failed",
                    "the host's control door failed; see the bridge's log",
                )
            )
        else:
            logger.info(
                "[link-bridge] command %s (call %d): %s on %s -> %s",
                request_id,
                call_id,
                request.action.value,
                request.bot_id,
                reply.status.value,
            )
            self._send({"type": "result", "id": call_id, "data": {"reply": message}})
            with self._lock:
                self.served += 1
        finally:
            with self._lock:
                self._pending.pop(call_id, None)
