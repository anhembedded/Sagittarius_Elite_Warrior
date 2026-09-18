"""strategy's write side: arming and disarming the one live strategy.

`EPIC-025E` PR 4.4f-2 — moved out of `binance_bot_module.py` alongside the
state singletons in `state_bindings.py`, for the same reason: deleting the
composition root itself is now the actual destination, so these two bindings
need a home regardless of the "second place to look" objection that kept
them there while nothing else changed.

`bind` (transient), matching every other command handler in this codebase.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy import (
    ArmStrategyCommand,
    ArmStrategyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.disarm_strategy import (
    DisarmStrategyCommand,
    DisarmStrategyCommandHandler,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_commands(container: IContainer) -> None:
    """Route each strategy command type to the handler that executes it."""
    container.bind(ArmStrategyCommand, ArmStrategyCommandHandler)
    container.bind(DisarmStrategyCommand, DisarmStrategyCommandHandler)
