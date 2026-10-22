"""`EPIC-038L`, `EPIC-045` - what each action of a host command may carry, and what it may not.

Split from `host_command_codec.py` when that file reached the 400-line ceiling: the codec is the wire
form (what the keys are, how a document is read and written); this is the policy per action (an edit
carries `set` and no venue, an add carries `entry` and the fixed `new-bot` subject, a confirm-resume may
carry `proposal`, an arm-strategy `strategy_venue`). A document that breaks one is *malformed*, never
widened. `action_problem` is the one entry point; a new action adds one function here and one line to its
chain.
"""

from __future__ import annotations

import re

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    ADD_SUBJECT,
    LOSS_CAP_SUBJECT,
    STRATEGY_SUBJECT,
    HostControlAction,
)
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    MAX_SETTINGS_PER_EDIT,
    ParameterSetting,
)

VENUE_SHAPE = re.compile(r"^[a-z0-9_]{1,32}$")
_PROPOSAL_SHAPE = re.compile(r"^[0-9a-f]{4,16}$")
_ENTRY_KEYS = frozenset({"name", "kind", "venue", "symbol", "params"})


def action_problem(
    document: dict[str, object], action: str, venue: object, bot_id: str
) -> str | None:
    """Why `document` may not carry what it carries for `action`; `None` when it may."""
    return (
        _edit_problem(document, action, venue)
        or _add_problem(document, action, venue, bot_id)
        or _delete_problem(action, venue)
        or _move_problem(document, action, venue)
        or _proposal_problem(document, action)
        or _strategy_problem(document, action, venue, bot_id)
        or _acknowledgement_problem(document, action, venue, bot_id)
    )


def _edit_problem(
    document: dict[str, object], action: str, venue: object
) -> str | None:
    """`set` is an edit's and only an edit's, and an edit places no order, so it names no venue."""
    if "set" not in document:
        return "an edit needs set" if action == "edit" else None
    if action != "edit":
        return "set belongs to an edit"
    if venue is not None:
        return "an edit asks no venue: confirmed_venue must be null"
    settings = document["set"]
    if (
        not isinstance(settings, dict)
        or not 1 <= len(settings) <= MAX_SETTINGS_PER_EDIT
    ):
        return f"set is not an object of 1 to {MAX_SETTINGS_PER_EDIT} settings"
    try:
        for key, value in settings.items():
            setting_of(key, value)
    except (TypeError, ValueError) as invalid:
        return f"set is not sound: {invalid}"
    return None


def _add_problem(
    document: dict[str, object], action: str, venue: object, bot_id: str
) -> str | None:
    """`entry` is an add's and only an add's; the bot it names does not exist yet and an add places no order."""
    named = bot_id == ADD_SUBJECT
    if action != HostControlAction.ADD.value:
        if "entry" in document:
            return "entry belongs to an add"
        return f"{ADD_SUBJECT} is not a bot id" if named else None
    if not named:
        return f"an add names no bot: bot_id is {ADD_SUBJECT}"
    if venue is not None:
        return "an add asks no venue: confirmed_venue must be null"
    if "entry" not in document:
        return "an add needs entry"
    return _entry_problem(document["entry"])


def _entry_problem(entry: object) -> str | None:
    if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
        return f"entry is not an object of exactly {', '.join(sorted(_ENTRY_KEYS))}"
    try:
        built_entry_of(entry)
    except (TypeError, ValueError) as invalid:
        return f"entry is not sound: {invalid}"
    return None


def _delete_problem(action: str, venue: object) -> str | None:
    """A delete forgets a bot at rest, sends nothing to the exchange and so asks no venue."""
    if action == HostControlAction.DELETE.value and venue is not None:
        return "a delete asks no venue: confirmed_venue must be null"
    return None


def _move_problem(
    document: dict[str, object], action: str, venue: object
) -> str | None:
    """`to_venue` is a move's and only a move's; a move places no order, so it asks no venue."""
    if action != HostControlAction.MOVE.value:
        return "to_venue belongs to a move" if "to_venue" in document else None
    if venue is not None:
        return "a move asks no venue: confirmed_venue must be null"
    target = document.get("to_venue")
    if not isinstance(target, str) or not VENUE_SHAPE.fullmatch(target):
        return "a move needs to_venue, a venue word"
    return None


def _proposal_problem(document: dict[str, object], action: str) -> str | None:
    """`proposal` is a confirm-resume's and only a confirm-resume's: the fingerprint of the proposal it lays.

    It may be absent (the host then refuses the confirmation in words, with the way to get one); when
    present it is a short hex digest, never text.
    """
    if "proposal" not in document:
        return None
    if action != HostControlAction.CONFIRM_RESUME.value:
        return "proposal belongs to a confirm-resume"
    found = document["proposal"]
    if not isinstance(found, str) or not _PROPOSAL_SHAPE.fullmatch(found):
        return "proposal is not a short hex fingerprint"
    return None


def _strategy_problem(
    document: dict[str, object], action: str, venue: object, bot_id: str
) -> str | None:
    """`strategy_venue` is an arm's and a disarm's and no other action's; both are about a venue's armed strategy, not a bot.

    An arm may carry the typed venue (a mainnet arm needs it, the host judges that); a disarm sells
    and cancels nothing, so it asks none.
    """
    named = bot_id == STRATEGY_SUBJECT
    arms = action == HostControlAction.ARM_STRATEGY.value
    disarms = action == HostControlAction.DISARM_STRATEGY.value
    if not (arms or disarms):
        if "strategy_venue" in document:
            return "strategy_venue belongs to an arm-strategy or a disarm-strategy"
        return f"{STRATEGY_SUBJECT} is not a bot id" if named else None
    if not named:
        return f"{action} names no bot: bot_id is {STRATEGY_SUBJECT}"
    target = document.get("strategy_venue")
    if not isinstance(target, str) or not VENUE_SHAPE.fullmatch(target):
        return f"{action} needs strategy_venue, a venue word"
    if disarms and venue is not None:
        return "a disarm-strategy asks no venue: confirmed_venue must be null"
    if "set" in document or "close_position" in document:
        return f"{action} carries no set or close_position"
    return None


def _acknowledgement_problem(
    document: dict[str, object], action: str, venue: object, bot_id: str
) -> str | None:
    """An acknowledgement is about the account and carries nothing a bot's command carries."""
    named = bot_id == LOSS_CAP_SUBJECT
    if action != HostControlAction.ACKNOWLEDGE_LOSS_CAP.value:
        return "loss-cap is not a bot id" if named else None
    if not named:
        return f"a loss-cap-ack names no bot: bot_id is {LOSS_CAP_SUBJECT}"
    if venue is not None or "close_position" in document or "set" in document:
        return "a loss-cap-ack carries no venue, close_position or set"
    return None


def setting_of(key: object, value: object) -> ParameterSetting:
    if not isinstance(key, str) or not isinstance(value, str):
        raise TypeError("a setting is text and text")
    return ParameterSetting(key, value)


def built_entry_of(entry: dict[str, object]) -> NewBotEntry:
    fields = [entry[name] for name in ("name", "kind", "venue", "symbol")]
    if not all(isinstance(field, str) for field in fields):
        raise TypeError("a field of the entry is not text")
    params = entry["params"]
    if not isinstance(params, dict):
        raise TypeError("params is not an object")
    name, kind, venue, symbol = (str(field) for field in fields)
    return NewBotEntry(
        name, kind, venue, symbol, tuple(setting_of(k, v) for k, v in params.items())
    )
