"""The wire form of a host command: one small JSON document, `sew.host-command/1` (`EPIC-038J`).

Strict on purpose. A file is read by a process that can stop a bot, so it accepts exactly the
keys below with exactly these types and nothing else: an unknown key, a bot id that is not
the shape of one, a timestamp with no zone, all make the document *malformed*, never
"close enough". `MalformedDocument.command_id` carries the id when that part was sound, so
the audit can say which command was refused.

@par The document
  schema          "sew.host-command/1"
  command_id      32 lower-case hex characters, chosen by the sender (the idempotency key)
  action          "stop" | "pause" | "resume" | "confirm-resume" | "start" | "edit" | "add" | "delete" | "move" | "arm-strategy" | "disarm-strategy" | "loss-cap-ack" | "refresh-facts"
  bot_id          1-64 characters of [a-z0-9_-] (a real bot id is six of [a-z0-9])
  confirmed_venue null, or the venue the operator typed (decision O8)
  issued_at       ISO 8601 with a time zone
  close_position  optional boolean, absent means false (`BUG-224`): a stop that closes the
                  position at market. It is written only when true, so a file that does not
                  ask for the close is byte-for-byte the document an older host reads.
  set             an edit's `--set key=value` pairs (`EPIC-038L`): an object of 1 to
                  `MAX_SETTINGS_PER_EDIT` text values, keys and values of the shape
                  `ParameterSetting` states. Required for "edit", refused for any other action.
                  An edit asks no venue: `confirmed_venue` must be null.
  to_venue        a move's target (`EPIC-045G`): a venue word of 1 to 32 characters of [a-z0-9_].
                  Required for "move", refused for any other action. A move asks no venue
                  (`confirmed_venue` must be null: it places no order, the real-money question is
                  at `bot start`) and names an existing bot.
  proposal        a confirm-resume's fingerprint (`EPIC-045G`, owner decision O3): 4 to 16 lower-case
                  hex characters, the digest `bot resume` printed for the proposal a person read.
                  Refused for any other action. Absent is a sound document: the host refuses the
                  confirmation in words.
  strategy_venue  an arm-strategy's or a disarm-strategy's venue (`EPIC-045G`): a venue word of 1 to
                  32 characters of [a-z0-9_]. Required for those two, refused for any other action,
                  and `bot_id` is then the fixed word `strategy`. An arm may carry `confirmed_venue`
                  (a mainnet arm needs it: the strategy then places orders on its own with real
                  money); a disarm asks none, it sells and cancels nothing.
  desired_state   an apply-entry's wish (`EPIC-045C`): "running" or "stopped". Required for "apply-entry",
                  refused for any other action; `bot_id` is then the fixed word `plan`, the entry
                  travels in `entry` (as an add's does), and `confirmed_venue` must be null: applying
                  places no order and starts nothing. An "unplan" names the bot whose wish is
                  forgotten and carries nothing else.
  entry           an add's bot (`EPIC-045A`): an object of exactly name, kind, venue, symbol and
                  params (an object of 0 to `MAX_SETTINGS_PER_EDIT` text values), each of the shape
                  `NewBotEntry` states. Required for "add", refused for any other action. An add
                  places no order and asks no venue: `confirmed_venue` must be null, and `bot_id`
                  is the fixed word `new-bot` (the host gives the bot its id). A "delete" names an
                  existing bot, asks no venue and carries nothing else.

@par Older hosts (`EPIC-038K`)
  `start` is a new `action` word, not a new key. An older host holds the closed set
  "stop | pause | resume" and reads a document with that word as *malformed* ("action is not
  one of ..."): it audits that, removes the file and executes nothing, so the operator gets
  REJECTED and no bot changes. A new host reads every document an older host wrote.

@par Older hosts (`EPIC-026L`)
  `loss-cap-ack` is a new `action` word, as `start` was: an older host reads the document as
  *malformed* ("action is not one of ..."), audits it and executes nothing, so the owner gets
  REJECTED and the cap stays tripped. It names no bot: `bot_id` is `loss-cap`, `confirmed_venue`
  is null and neither `close_position` nor `set` is present.

@par Older hosts (`EPIC-038L`)
  `edit` is a new `action` word *and* `set` is a new key. An older host checks the keys first and
  reads the document as *malformed* ("it has an unknown key (set)"): audited, removed, executed
  never, so the operator gets REJECTED and the bot keeps its parameters. A new host reads every
  document an older host wrote, because `set` is absent from them.

@par Older hosts (`EPIC-045C`)
  `apply-entry` and `unplan` are new `action` words and `desired_state` a new key: an older host reads
  them as *malformed* ("action is not one of ..." / "it has an unknown key (desired_state)"), audits
  the command and changes nothing, so the operator gets REJECTED and no plan entry is applied.

@par Older hosts (`EPIC-045G`, proposal)
  `proposal` is a new key on the existing `confirm-resume` word: an older host reads it as *malformed*
  ("it has an unknown key (proposal)"), audits it and lays nothing.

@par Older hosts (`EPIC-045G`, arm-strategy and disarm-strategy)
  Both are new `action` words and `strategy_venue` is a new key: an older host reads a document with
  it as *malformed* ("it has an unknown key (strategy_venue)"), audits it and arms or disarms nothing.

@par Older hosts (`EPIC-045G`, confirm-resume)
  `confirm-resume` is a new `action` word and adds no key: an older host reads it as *malformed*
  ("action is not one of ..."), audits it, removes the file and executes nothing, so the operator
  gets REJECTED and no ladder is laid. A new host reads every document an older host wrote.

@par Older hosts (`EPIC-045G`)
  `move` is a new `action` word and `to_venue` a new key: an older host reads it as *malformed*
  ("it has an unknown key (to_venue)"), audits it and moves nothing.

@par Older hosts (`EPIC-045`)
  `add` and `delete` are new `action` words, and `entry` is a new key: an older host reads an add
  as *malformed* ("it has an unknown key (entry)") and a delete as *malformed* ("action is not one
  of ..."), audits it, removes the file and executes nothing, so the operator gets REJECTED and
  no bot is created or forgotten. A new host reads every document an older host wrote.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
)
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_rules import (
    VENUE_SHAPE,
    action_problem,
    built_entry_of,
    setting_of,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    HOST_COMMAND_SCHEMA,
    HostCommand,
)

_ID_SHAPE = re.compile(r"^[0-9a-f]{32}$")
_BOT_SHAPE = re.compile(r"^[a-z0-9_-]{1,64}$")
_KEYS = frozenset(
    {
        "schema",
        "command_id",
        "action",
        "bot_id",
        "confirmed_venue",
        "issued_at",
        "close_position",
        "set",
        "entry",
        "to_venue",
        "proposal",
        "strategy_venue",
        "desired_state",
    }
)


@dataclass(frozen=True, slots=True)
class MalformedDocument:
    """Why a document is not a command; never the document's own text."""

    reason: str
    command_id: str = ""


def encode_command(command: HostCommand) -> str:
    document: dict[str, object] = {
        "schema": HOST_COMMAND_SCHEMA,
        "command_id": command.command_id,
        "action": command.action.value,
        "bot_id": command.bot_id,
        "confirmed_venue": command.confirmed_venue,
        "issued_at": command.issued_at.isoformat(),
    }
    if command.close_position:
        document["close_position"] = True
    if command.settings:
        document["set"] = {setting.key: setting.value for setting in command.settings}
    if command.to_venue is not None:
        document["to_venue"] = command.to_venue
    if command.proposal is not None:
        document["proposal"] = command.proposal
    if command.strategy_venue is not None:
        document["strategy_venue"] = command.strategy_venue
    if command.desired_state is not None:
        document["desired_state"] = command.desired_state
    if command.entry is not None:
        document["entry"] = {
            "name": command.entry.name,
            "kind": command.entry.kind,
            "venue": command.entry.venue,
            "symbol": command.entry.symbol,
            "params": {s.key: s.value for s in command.entry.params},
        }
    return json.dumps(document, sort_keys=True)


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
        close_position=document.get("close_position", False),
        settings=_settings_of(document.get("set")),
        entry=_entry_of(document.get("entry")),
        to_venue=document.get("to_venue"),
        proposal=document.get("proposal"),
        strategy_venue=document.get("strategy_venue"),
        desired_state=document.get("desired_state"),
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
        return f"action is not one of {', '.join(a.value for a in HostControlAction)}"
    bot_id = document.get("bot_id")
    if not isinstance(bot_id, str) or not _BOT_SHAPE.fullmatch(bot_id):
        return "bot_id is not the shape of a bot id"
    venue = document.get("confirmed_venue")
    if venue is not None and (
        not isinstance(venue, str) or not VENUE_SHAPE.fullmatch(venue)
    ):
        return "confirmed_venue is neither null nor a venue word"
    close = document.get("close_position", False)
    if not isinstance(close, bool):
        return "close_position is not true or false"
    if close and action != "stop":
        return "close_position belongs to a stop"
    problem = action_problem(document, action, venue, bot_id)
    if problem is not None:
        return problem
    return _timestamp_problem(document.get("issued_at"))


def _timestamp_problem(value: object) -> str | None:
    if not isinstance(value, str):
        return "issued_at is not a timestamp"
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return "issued_at is not a timestamp"
    return None if moment.tzinfo is not None else "issued_at has no time zone"


def _settings_of(raw: object) -> tuple[ParameterSetting, ...]:
    """The settings of a document `_problem_of` found sound (absent for every action but an edit)."""
    if not isinstance(raw, dict):
        return ()
    return tuple(setting_of(key, value) for key, value in raw.items())


def _entry_of(raw: object) -> NewBotEntry | None:
    """The entry of a document `_problem_of` found sound (absent for every action but an add)."""
    return built_entry_of(raw) if isinstance(raw, dict) else None
