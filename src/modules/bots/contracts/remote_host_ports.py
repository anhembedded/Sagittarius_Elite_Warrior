"""`EPIC-047E` — what a dispatcher for a remote host reaches it through, as one value.

@details The shell owns the link and the module owns the dispatcher, so the shell hands the module these four ports and the
module builds the dispatcher (`module.py` → `remote_bots_dispatcher`). `local` answers what needs no host (the pure
assessment), `unanswered` is the list of commands whose outcome the desktop does not know.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_host_control import IHostControl
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_host_world import IHostWorld
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_unanswered_commands import (
    IUnansweredCommands,
)


@dataclass(frozen=True, slots=True)
class RemoteHostPorts:
    world: IHostWorld
    control: IHostControl
    unanswered: IUnansweredCommands
    local: ICommandDispatcher
