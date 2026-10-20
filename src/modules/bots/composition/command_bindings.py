"""bots' write side: one handler per lifecycle command (`EPIC-029B`).

`bind` (transient), matching every other command handler in this codebase.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.acknowledge_loss_cap_for_host import (
    AcknowledgeLossCapForHostCommandHandler,
)
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
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot_for_host import (
    EditBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot import (
    PauseBotCommand,
    PauseBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot_for_host import (
    PauseBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
    ResumeBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot_for_host import (
    ResumeBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_halted_for_host import (
    ResumeHaltedForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_recovering_for_host import (
    ResumeRecoveringForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
    StartBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot_for_host import (
    StartBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
    StopBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot_for_host import (
    StopBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot_for_operator import (
    StopBotForOperatorCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    AcknowledgeLossCapForHostCommand,
    EditBotForHostCommand,
    PauseBotForHostCommand,
    ResumeBotForHostCommand,
    ResumeHaltedForHostCommand,
    ResumeRecoveringForHostCommand,
    StartBotForHostCommand,
    StopBotForHostCommand,
    StopBotForOperatorCommand,
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
    # `EPIC-038D` - what the `run` host asks, answered by the screen's own commands.
    container.bind(StartBotForHostCommand, StartBotForHostCommandHandler)
    container.bind(StopBotForHostCommand, StopBotForHostCommandHandler)
    container.bind(
        ResumeRecoveringForHostCommand, ResumeRecoveringForHostCommandHandler
    )
    container.bind(ResumeHaltedForHostCommand, ResumeHaltedForHostCommandHandler)
    # `EPIC-038J` - what a person sends to the running host (`bot stop`, `bot pause`, `bot resume`).
    container.bind(StopBotForOperatorCommand, StopBotForOperatorCommandHandler)
    container.bind(PauseBotForHostCommand, PauseBotForHostCommandHandler)
    container.bind(ResumeBotForHostCommand, ResumeBotForHostCommandHandler)
    # `EPIC-038K` - `bot start` reuses `StartBotForHostCommand` bound above.
    # `EPIC-038L` - `bot edit` on the running host; the screen's `EditBotCommand` is bound above.
    container.bind(EditBotForHostCommand, EditBotForHostCommandHandler)
    # `EPIC-026L` - the owner's `bot loss-cap-ack` on the running host.
    container.bind(
        AcknowledgeLossCapForHostCommand, AcknowledgeLossCapForHostCommandHandler
    )
