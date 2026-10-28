"""`EPIC-047E` — the Bots screen's commands as the host's requests, and the host's replies as the screen's results.

@details The screen sends the commands it always sent (`StopBotCommand`, `StartBotCommand`, ...); the
VPS tab's dispatcher turns each into the request the `bot` verb of the same name would send
(`cli/bot_control_verbs.py`), so the host runs the very command the Bots tab dispatches, behind its own
gate and its audit. This file decides nothing about money: where a command asks the real-money question the
screen already asked it, the answer travels as the venue typed (`confirmed_venue`), exactly as `--confirm-venue`
does, and the host judges it (decision O8).

@par What the VPS tab does not carry, and says so
  · a Start with unsaved edits: the in-process Start saves them only if the bot is ready with them, which
    two requests cannot promise, so it is refused with the words to Save first;
  · a rename: the screen never sends one, and the host's edit has no name.

@par Extension cases
  · a new action of the screen — one case in `request_of` and one `HostControlAction` already on the host.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    ADD_SUBJECT,
    HostControlAction,
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.change_bot_venue import (
    ChangeBotVenueCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume import (
    ConfirmBotResumeCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot import (
    DeleteBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot import (
    EditBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot import (
    PauseBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.resume_proposal_summary import (
    FINGERPRINT_LENGTH,
)

NOT_CARRIED_START_EDITS = "Save the changes first, then Start: a Start from the VPS tab does not carry unsaved edits to the host."
NOT_CARRIED_RENAME = "A bot cannot be renamed from the VPS tab."
UNKNOWN_BOT = "this bot is not in the host's list (it may have been deleted)"
_NOT_OFFERED = "the VPS tab does not offer this: "


class NotOfferedInVpsTabError(LookupError):
    """A query or command the VPS tab does not carry to the host (the Backtest workbench, the plan file)."""

    def __init__(self, message: object) -> None:
        super().__init__(f"{_NOT_OFFERED}{type(message).__name__}")


@dataclass(frozen=True, slots=True)
class NothingToSend:
    """The command asks for no change; it is answered without a request."""

    result: BotCommandResult


type Translated = HostControlRequest | NothingToSend


def request_of(
    command: object, bots: Mapping[str, BotSnapshot]
) -> Translated | BotCommandResult:
    """The host's request for `command`, a result when the command cannot be sent as it is.

    `bots` are the host's bots as the desktop last heard them: a command on a bot looks its venue and
    settings up there, and a bot that is not there is refused in words rather than sent blind."""
    if isinstance(command, CreateBotCommand):
        return _add(command)
    bot_id = getattr(command, "bot_id", None)
    if not isinstance(bot_id, str):
        raise NotOfferedInVpsTabError(command)
    bot = bots.get(bot_id)
    if bot is None:
        return BotCommandResult.refused(BotRefusal.NOT_FOUND, UNKNOWN_BOT, bot_id)
    return _on_bot(command, bot)


def _on_bot(command: object, bot: BotSnapshot) -> Translated | BotCommandResult:
    venue = bot.venue.value
    if isinstance(command, StopBotCommand):
        return HostControlRequest(
            HostControlAction.STOP,
            bot.bot_id,
            venue if command.real_money_confirmed else None,
            close_position=command.base is ExposureHandling.CLOSE_AT_MARKET,
        )
    if isinstance(command, StartBotCommand):
        if command.config is not None:
            return BotCommandResult.refused(
                BotRefusal.PARAMETERS_REFUSED, NOT_CARRIED_START_EDITS, bot.bot_id
            )
        return HostControlRequest(
            HostControlAction.START,
            bot.bot_id,
            venue if command.real_money_confirmed else None,
        )
    if isinstance(command, ResumeBotCommand):
        return HostControlRequest(
            HostControlAction.RESUME,
            bot.bot_id,
            venue if command.real_money_confirmed else None,
        )
    if isinstance(command, ConfirmBotResumeCommand):
        # The screen asked its question before it built this command; the host judges the typed venue.
        return HostControlRequest(
            HostControlAction.CONFIRM_RESUME,
            bot.bot_id,
            venue,
            proposal=command.proposal,
        )
    if isinstance(command, PauseBotCommand):
        return HostControlRequest(HostControlAction.PAUSE, bot.bot_id)
    if isinstance(command, DeleteBotCommand):
        return HostControlRequest(HostControlAction.DELETE, bot.bot_id)
    if isinstance(command, ChangeBotVenueCommand):
        return HostControlRequest(
            HostControlAction.MOVE, bot.bot_id, to_venue=command.venue.value
        )
    if isinstance(command, EditBotCommand):
        return _edit(command, bot)
    raise NotOfferedInVpsTabError(command)


def _edit(command: EditBotCommand, bot: BotSnapshot) -> Translated | BotCommandResult:
    if command.name != bot.name:
        return BotCommandResult.refused(
            BotRefusal.INVALID_DEFINITION, NOT_CARRIED_RENAME, bot.bot_id
        )
    changed = tuple(
        ParameterSetting(key, value)
        for key, value in command.config.items()
        if bot.config.get(key) != value
    )
    if not changed:
        return NothingToSend(BotCommandResult.done(bot.bot_id))
    return HostControlRequest(HostControlAction.EDIT, bot.bot_id, settings=changed)


def _add(command: CreateBotCommand) -> HostControlRequest:
    entry = NewBotEntry(
        command.name,
        command.kind,
        command.venue.value,
        command.symbol,
        tuple(ParameterSetting(k, v) for k, v in command.config.items()),
    )
    return HostControlRequest(HostControlAction.ADD, ADD_SUBJECT, entry=entry)


_FINGERPRINT = re.compile(rf"\bFingerprint ([0-9a-f]{{{FINGERPRINT_LENGTH}}})\b")


def proposal_in(words: str) -> str | None:
    """The fingerprint of the resume proposal the host's reply describes, or `None`.

    The host's Resume of a HALTED bot answers with the proposal in words, "Fingerprint 1a2b3c4d" among them
    (`resume_bot_for_host`); the Bots tab's Confirm resume names no proposal, the host's confirmation requires one,
    so the VPS tab confirms the one it was shown. A test pins this reading against the host's own sentence."""
    found = _FINGERPRINT.search(words)
    return found.group(1) if found else None


def result_of(request: HostControlRequest, reply: HostControlReply) -> BotCommandResult:
    """The screen's result for the host's reply: the host's own words, whatever came back.

    A refusal carries no `BotRefusal`: the host refused in words, and the wire has no code for which
    gate said no. The screen shows the words (it reads no code), and a code invented here would
    claim a reason the host never gave."""
    bot_id = reply.bot_id or request.bot_id
    if reply.status is HostControlStatus.DONE:
        return BotCommandResult(accepted=True, bot_id=bot_id, message=reply.message)
    return BotCommandResult(
        accepted=False, bot_id=request.bot_id, refusal=None, message=reply.message
    )
