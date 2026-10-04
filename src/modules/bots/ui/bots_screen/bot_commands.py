"""`EPIC-029F` — the command a click sends, after asking what it must ask.

Stop asks what to do with the base (O3), Delete asks to confirm; a cancelled
question sends nothing, and the screen stays exactly as it was. Save sends
the parameters on screen.
"""

from __future__ import annotations

from collections.abc import Mapping

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


def command_for(
    action: BotAction,
    bot: BotSnapshot,
    dialogs: BotsDialogs,
    edited: Mapping[str, str] | None = None,
) -> object | None:
    """The command for `action` on `bot`, or `None` when the user cancelled."""
    bot_id = bot.bot_id
    if action is BotAction.STOP:
        base = dialogs.ask_stop(bot)
        return StopBotCommand(bot_id, base) if base is not None else None
    if action is BotAction.DELETE:
        return DeleteBotCommand(bot_id) if dialogs.confirm_delete(bot) else None
    if action is BotAction.SAVE:
        return EditBotCommand(bot_id, bot.name, dict(edited or bot.config))
    return {
        BotAction.START: StartBotCommand,
        BotAction.PAUSE: PauseBotCommand,
        BotAction.RESUME: ResumeBotCommand,
        BotAction.CONFIRM_RESUME: ConfirmBotResumeCommand,
    }[action](bot_id)
