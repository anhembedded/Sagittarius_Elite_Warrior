"""`EPIC-029F` — the command a click sends, after asking what it must ask.

Stop asks what to do with the base (O3), Delete asks to confirm; a cancelled
question sends nothing, and the screen stays exactly as it was. Save sends
the parameters on screen; so does Start (Save and start, D8) when they differ
from the saved ones.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume import (
    ConfirmBotResumeCommand,
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_dialogs import (
    BotsDialogs,
)


@dataclass(frozen=True, slots=True)
class PendingAction:
    """The action in flight. What the screen does once it settles follows
    `action`, never the words of `label` (PR #333 review)."""

    label: str
    #: `None` while a new bot is being created, or moved to another venue.
    action: BotAction | None = None
    #: A draft is being moved to another Spot venue (`BOT-171`).
    moves_venue: bool = False

    @property
    def creates_bot(self) -> bool:
        """The command makes a new bot, which the screen then selects."""
        return self.action is None and not self.moves_venue


#: The actions after which orders flow.
_STARTS_TRADING = frozenset(
    {BotAction.START, BotAction.RESUME, BotAction.CONFIRM_RESUME}
)


def command_for(
    action: BotAction,
    bot: BotSnapshot,
    dialogs: BotsDialogs,
    edited: Mapping[str, str] | None = None,
) -> object | None:
    """The command for `action` on `bot`, or `None` when the user cancelled."""
    bot_id = bot.bot_id
    if action in _STARTS_TRADING and not dialogs.allow_real_money(
        bot.venue, "start this bot"
    ):
        return None
    if action is BotAction.STOP:
        base = dialogs.ask_stop(bot)
        return StopBotCommand(bot_id, base) if base is not None else None
    if action is BotAction.DELETE:
        return DeleteBotCommand(bot_id) if dialogs.confirm_delete(bot) else None
    if action is BotAction.SAVE:
        return EditBotCommand(bot_id, bot.name, dict(edited or bot.config))
    if action is BotAction.START:
        # Save and start (`EPIC-034H`, D8): the edits on screen travel with the
        # start, which saves them only when the bot is ready with them.
        unsaved = edited is not None and dict(edited) != dict(bot.config)
        # Reaching here, `allow_real_money` answered yes: the use case enforces it.
        return StartBotCommand(
            bot_id,
            dict(edited) if unsaved and edited else None,
            real_money_confirmed=True,
        )
    return {
        BotAction.PAUSE: PauseBotCommand,
        BotAction.RESUME: ResumeBotCommand,
        BotAction.CONFIRM_RESUME: ConfirmBotResumeCommand,
    }[action](bot_id)
