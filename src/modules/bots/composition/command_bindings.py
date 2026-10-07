"""bots' write side: one handler per lifecycle command (`EPIC-029B`).

`bind` (transient), matching every other command handler in this codebase.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.change_bot_venue import (
    ChangeBotVenueCommand,
    ChangeBotVenueCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume import (
    ConfirmBotResumeCommand,
    ConfirmBotResumeCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
    CreateBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot import (
    DeleteBotCommand,
    DeleteBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot import (
    EditBotCommand,
    EditBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot import (
    PauseBotCommand,
    PauseBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
    ResumeBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
    StartBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
    StopBotCommandHandler,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_commands(container: IContainer) -> None:
    container.bind(CreateBotCommand, CreateBotCommandHandler)
    container.bind(EditBotCommand, EditBotCommandHandler)
    container.bind(ChangeBotVenueCommand, ChangeBotVenueCommandHandler)
    container.bind(StartBotCommand, StartBotCommandHandler)
    container.bind(PauseBotCommand, PauseBotCommandHandler)
    container.bind(ResumeBotCommand, ResumeBotCommandHandler)
    container.bind(StopBotCommand, StopBotCommandHandler)
    container.bind(ConfirmBotResumeCommand, ConfirmBotResumeCommandHandler)
    container.bind(DeleteBotCommand, DeleteBotCommandHandler)
