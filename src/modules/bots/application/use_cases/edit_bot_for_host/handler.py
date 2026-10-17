"""`EPIC-038L` - the host's "change these parameters of this bot", answered by the screen's own Save.

The owner runs several bots on one host and corrects one that is at rest (a lower bound the price
has left, `bot start` refused it) without stopping the others. `bot apply` needs the data root's
writable lock, which the host holds; this handler is the same edit reached through the command
directory. It adds no way to edit a bot: it merges the operator's `--set` settings into the bot's
parameters and dispatches the very `EditBotCommand` the Bots tab and `bot apply` dispatch, so the
lifecycle table (`permits_edit`: DRAFT and STOPPED), the unchangeable kind, venue and symbol, and "an
edit lands the bot on DRAFT" are theirs (P5).

Order, so that a refusal changes nothing and says why:
  1. the bot exists, and the lifecycle table lets a bot in its state be edited (the refusal says what
     to do first, in the words of the state);
  2. the settings are sound as a set: at least one, no key twice, no more than `MAX_SETTINGS_PER_EDIT`;
  3. the bot's kind judges the changed parameters without the exchange (`IBotKind.parameter_problem`):
     an unknown key or an unreadable value is refused in words;
  4. a set that changes nothing is refused: a STOPPED bot would otherwise land on DRAFT for no reason;
  5. the edit is dispatched, and the reply names each `key old -> new`.

An edit places no order and needs no `--confirm-venue`, on a mainnet venue too: the money question
stays at `bot start`, whose guard is untouched.

@par Concurrency
Steps 1-5 run under `BotCommandLock`, the lock a Start holds while it reads the bots and moves one
to STARTING, so an edit cannot interleave with a start: either the Start has already moved the bot
(the edit is refused, the bot is STARTING) or the edit has landed first (the Start reads the new
parameters). A bot at rest has no executor and no worker, so it has no queue to run on; the write is
the one the Bots tab's Save makes.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    MAX_SETTINGS_PER_EDIT,
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot import (
    EditBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    EditBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
    UnknownBotKindError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
    is_declared,
    permits_edit,
)

_UNSET = "(unset)"
_PLAN_REMINDER = (
    "update the same value in your plan file too: the next `bot apply` of the old plan edits the "
    "bot back"
)


class EditBotForHostCommandHandler(
    ICommandHandler[EditBotForHostCommand, BotCommandResult]
):
    def __init__(
        self,
        store: IBotStore,
        dispatcher: ICommandDispatcher,
        kinds: IBotKindCatalog,
        lock: BotCommandLock,
    ) -> None:
        self._lookup = BotLookup(store)
        self._dispatcher = dispatcher
        self._kinds = kinds
        self._lock = lock

    def execute(self, command: EditBotForHostCommand) -> BotCommandResult:
        with self._lock.held():
            found = self._lookup.find(command.bot_id)
            if isinstance(found, BotCommandResult):
                return found
            bot = found.bot
            if not permits_edit(bot.state):
                return self._refused(
                    command,
                    BotRefusal.INVALID_TRANSITION,
                    _not_at_rest(command, bot.state),
                )
            problem = _set_problem(command.settings)
            if problem:
                return self._refused(command, BotRefusal.INVALID_DEFINITION, problem)
            merged = {**bot.definition.config, **_as_mapping(command.settings)}
            problem = self._parameter_problem(bot.definition.kind, merged, command)
            if problem:
                return self._refused(command, BotRefusal.INVALID_DEFINITION, problem)
            changes = _changes(bot.definition.config, command.settings)
            if not changes:
                return self._refused(
                    command,
                    BotRefusal.INVALID_DEFINITION,
                    "those values are already the bot's: nothing to change",
                )
            result = cast(
                BotCommandResult,
                self._dispatcher.dispatch(
                    EditBotCommand,
                    EditBotCommand(command.bot_id, bot.definition.name, merged),
                ),
            )
            if not result.accepted:
                return result
            return BotCommandResult(
                accepted=True,
                bot_id=command.bot_id,
                message=_accepted_words(changes, bot.state),
            )

    def _parameter_problem(
        self, kind_id: str, merged: dict[str, str], command: EditBotForHostCommand
    ) -> str:
        try:
            kind = self._kinds.kind(kind_id)
        except UnknownBotKindError:
            return f"this build has no kind of bot {kind_id!r}, so it cannot judge the change"
        problem = kind.parameter_problem(
            merged, [setting.key for setting in command.settings]
        )
        return problem or ""

    @staticmethod
    def _refused(
        command: EditBotForHostCommand, refusal: BotRefusal, words: str
    ) -> BotCommandResult:
        return BotCommandResult.refused(
            refusal, f"{words} Nothing was changed.", command.bot_id
        )


def _not_at_rest(command: EditBotForHostCommand, state: BotLifecycleState) -> str:
    stoppable = is_declared(state, BotLifecycleEvent.STOP) and (
        state is not BotLifecycleState.STOPPING
    )
    way = (
        "Stop it first (`bot stop`), then edit it when it is STOPPED."
        if stoppable
        else "Wait until it is STOPPED (see `bot show`)."
    )
    return f"Bot {command.bot_id} is {state.value}: only a DRAFT or STOPPED bot can be edited. {way}"


def _set_problem(settings: tuple[ParameterSetting, ...]) -> str:
    if not settings:
        return "bot edit needs at least one --set key=value."
    if len(settings) > MAX_SETTINGS_PER_EDIT:
        return f"bot edit takes at most {MAX_SETTINGS_PER_EDIT} settings, not {len(settings)}."
    keys = [setting.key for setting in settings]
    repeated = sorted({key for key in keys if keys.count(key) > 1})
    if repeated:
        return f"{', '.join(repeated)} is set more than once; set each parameter once."
    return ""


def _as_mapping(settings: tuple[ParameterSetting, ...]) -> dict[str, str]:
    return {setting.key: setting.value for setting in settings}


def _changes(
    held: Mapping[str, str], settings: tuple[ParameterSetting, ...]
) -> list[tuple[str, str, str]]:
    """`(key, old, new)` for each setting that differs from what the bot holds."""
    return [
        (setting.key, held.get(setting.key, _UNSET), setting.value)
        for setting in settings
        if held.get(setting.key) != setting.value
    ]


def _accepted_words(changes: list[tuple[str, str, str]], was: BotLifecycleState) -> str:
    moved = ", ".join(f"{key} {old} -> {new}" for key, old, new in changes)
    return (
        f"{moved}. The bot is DRAFT (it was {was.value}) and starts only when you `bot start` it; "
        f"{_PLAN_REMINDER}"
    )
