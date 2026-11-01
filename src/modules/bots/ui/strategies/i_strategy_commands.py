"""What the Bots presenter needs of its strategy commands: bind them, and subscribe what they listen to.

@details A `Protocol`, because both implementers are `QObject`s (`architecture-rule.md` §2.1, reason (a)): `VenueStrategies`
arms this computer's own venues; `HostStrategies` (`EPIC-047E`) asks the VPS host to arm or disarm the strategy it holds.
The presenter and `bind_bots_commands` know only this.

@par Extension cases
  · a third place strategies live - one more class with these two members, chosen by `BotsBackend.strategies`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)


@runtime_checkable
class IStrategyCommands(Protocol):
    @property
    def subscriptions(self) -> tuple[tuple[type, Callable[..., None]], ...]:
        """What the presenter subscribes for its lifetime: `(event type, handler)`."""
        ...

    def bind_commands(
        self, binder: ICommandBinder, arm_id: str, disarm_id: str
    ) -> None:
        """Binds Arm strategy and Disarm strategy under the ids the presenter's commands carry."""
        ...
