"""The wire form of a host command: one small JSON document, `sew.host-command/1` (`EPIC-038J`).

Strict on purpose. A file is read by a process that can stop a bot, so it accepts exactly the
keys below with exactly these types and nothing else: an unknown key, a bot id that is not
the shape of one, a timestamp with no zone, all make the document *malformed*, never
"close enough". `MalformedDocument.command_id` carries the id when that part was sound, so
the audit can say which command was refused.

@par The document
  schema          "sew.host-command/1"
  command_id      32 lower-case hex characters, chosen by the sender (the idempotency key)
  action          "stop" | "pause" | "resume"
  bot_id          1-64 characters of [a-z0-9_-] (a real bot id is six of [a-z0-9])
  confirmed_venue null, or the venue the operator typed (decision O8)
  issued_at       ISO 8601 with a time zone
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    HOST_COMMAND_SCHEMA,
    HostCommand,
)

_ID_SHAPE = re.compile(r"^[0-9a-f]{32}$")
_BOT_SHAPE = re.compile(r"^[a-z0-9_-]{1,64}$")
_VENUE_SHAPE = re.compile(r"^[a-z0-9_]{1,32}$")
_KEYS = frozenset(
    {"schema", "command_id", "action", "bot_id", "confirmed_venue", "issued_at"}
)


@dataclass(frozen=True, slots=True)
class MalformedDocument:
    """Why a document is not a command; never the document's own text."""

    reason: str
    command_id: str = ""


def encode_command(command: HostCommand) -> str:
    return json.dumps(
        {
            "schema": HOST_COMMAND_SCHEMA,
            "command_id": command.command_id,
            "action": command.action.value,
            "bot_id": command.bot_id,
            "confirmed_venue": command.confirmed_venue,
            "issued_at": command.issued_at.isoformat(),
        },
        sort_keys=True,
    )


def parse_command(text: str) -> HostCommand | MalformedDocument:
    try:
        document = json.loads(text)
    except ValueError:
        return MalformedDocument("it is not JSON")
    if not isinstance(document, dict):
        return MalformedDocument("it is not a JSON object")
    command_id = _sound_id(document)
    problem = _problem_of(document)
    if problem is not None:
        return MalformedDocument(problem, command_id)
    return HostCommand(
        command_id=command_id,
        action=HostControlAction(document["action"]),
        bot_id=document["bot_id"],
        confirmed_venue=document["confirmed_venue"],
        issued_at=datetime.fromisoformat(document["issued_at"]),
    )


def _sound_id(document: dict[str, object]) -> str:
    found = document.get("command_id")
    return found if isinstance(found, str) and _ID_SHAPE.fullmatch(found) else ""


def _problem_of(document: dict[str, object]) -> str | None:
    unknown = set(document) - _KEYS
    if unknown:
        return f"it has an unknown key ({min(unknown)[:32]})"
    if document.get("schema") != HOST_COMMAND_SCHEMA:
        return f"its schema is not {HOST_COMMAND_SCHEMA}"
    if not _sound_id(document):
        return "command_id is not 32 hex characters"
    action = document.get("action")
    if not isinstance(action, str) or action not in {
        a.value for a in HostControlAction
    }:
        return "action is not one of stop, pause, resume"
    bot_id = document.get("bot_id")
    if not isinstance(bot_id, str) or not _BOT_SHAPE.fullmatch(bot_id):
        return "bot_id is not the shape of a bot id"
    venue = document.get("confirmed_venue")
    if venue is not None and (
        not isinstance(venue, str) or not _VENUE_SHAPE.fullmatch(venue)
    ):
        return "confirmed_venue is neither null nor a venue word"
    return _timestamp_problem(document.get("issued_at"))


def _timestamp_problem(value: object) -> str | None:
    if not isinstance(value, str):
        return "issued_at is not a timestamp"
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return "issued_at is not a timestamp"
    return None if moment.tzinfo is not None else "issued_at has no time zone"
