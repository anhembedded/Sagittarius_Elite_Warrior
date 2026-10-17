"""`bot stop`, `bot pause` and `bot resume` as a `Report` (`EPIC-038J`).

The payload is the contract with scripts (`sew.bot-control/1`): a key is added within a version,
never renamed. It holds the action, the bot, how the request ended, the host's sentence and the
command id (the key to the host's audit); no secret.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlRequest,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    JsonValue,
    Report,
    ReportRow,
    ReportSection,
)

CONTROL_COMMAND = "bot-control"
SCHEMA_VERSION = 1


def control_report(request: HostControlRequest, reply: HostControlReply) -> Report:
    payload: dict[str, JsonValue] = {
        "action": request.action.value,
        "bot_id": request.bot_id,
        "status": reply.status.value,
        "message": reply.message,
        "command_id": reply.command_id,
    }
    heading = f"bot {request.action.value} {request.bot_id}"
    layout = (ReportSection(None, (ReportRow.of(f"{heading}: {reply.message}"),)),)
    return Report(CONTROL_COMMAND, SCHEMA_VERSION, payload, layout)
