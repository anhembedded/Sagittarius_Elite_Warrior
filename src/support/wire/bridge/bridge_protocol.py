"""`EPIC-047C` — the bridge protocol's fixed words: exit statuses, cadences, root names, the error a call can end in."""

from __future__ import annotations

import json
import math
from typing import Final

#: Exit statuses of the bridge process. `EXIT_REFUSED` is the one the desktop's words explain.
EXIT_ENDED: Final = 0
EXIT_REFUSED: Final = 3
EXIT_PROTOCOL: Final = 4
EXIT_IDLE: Final = 6

HEARTBEAT_S: Final = 2.0
IDLE_WATCHDOG_S: Final = 6.0
HELLO_TIMEOUT_S: Final = 10.0
#: The spike's cadence (DERISK R5: one `scandir` every 100 ms, p50 52 ms, p95 100 ms).
POLL_S: Final = 0.1
FACTS_LOOK_S: Final = 1.0
DEFAULT_COMMAND_WAIT_S: Final = 5.0
MAX_COMMAND_WAIT_S: Final = 30.0
MAX_PENDING_COMMANDS: Final = 4
REQUEST_ROOT: Final = "sew.host-control-request/1"
REPLY_ROOT: Final = "sew.host-control-reply/1"
MESSAGE_LIMIT: Final = 200


class CallError(Exception):
    """A call that cannot be served; the code and the words go back as an `error`."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def parse_line(line: str) -> dict[str, object]:
    try:
        document = json.loads(line)
    except ValueError as failure:
        raise CallError("bad_json", "a line is one JSON object") from failure
    if type(document) is not dict:
        raise CallError("bad_json", "a line is one JSON object")
    return document


def wait_of(raw: object) -> float:
    if type(raw) not in (int, float) or not math.isfinite(raw):  # type: ignore[arg-type]
        raise CallError("bad_command", "wait_s is a number of seconds")
    seconds = float(raw)  # type: ignore[arg-type]
    if not 0 <= seconds <= MAX_COMMAND_WAIT_S:
        raise CallError(
            "bad_command", f"wait_s is between 0 and {MAX_COMMAND_WAIT_S:g} seconds"
        )
    return seconds


def error_message(call_id: int, code: str, message: str) -> dict[str, object]:
    return {"type": "error", "id": call_id, "code": code, "message": message}
