"""`EPIC-047E` — the bridge's `outcome` call: what the host recorded for a command id, read-only.

@details `{"type":"call","id":n,"method":"outcome","params":{"request_id":<32 hex>}}` is answered by
`{"reply": <sew.host-control-reply/1> | null}`: the recorded outcome (or, in words, that the command still waits for the
host), and `null` when the host has never seen the id. The desktop asks it after a reconnect for a command whose answer was
lost with the link, so it learns what happened without sending anything again (decision of 2026-10-28, `EPIC-047E`: a lost
command is never re-executed by itself). It reads the host's audit and control directory and writes nothing, so it runs on
the session's thread like `snapshot`.
"""

from __future__ import annotations

import re
from typing import Final

from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    REPLY_ROOT,
    CallError,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_command_door import (
    ICommandDoor,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots

_REQUEST_ID: Final = re.compile(r"[0-9a-f]{32}")


def serve_outcome(
    door: ICommandDoor, roots: WireRoots, params: dict[str, object]
) -> dict[str, object]:
    request_id = params.get("request_id")
    if type(request_id) is not str or not _REQUEST_ID.fullmatch(request_id):
        raise CallError("bad_outcome", "request_id is 32 lowercase hex characters")
    reply = door.outcome_of(request_id)
    return {"reply": None if reply is None else roots.encode(REPLY_ROOT, reply)}
