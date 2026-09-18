"""`IArmedStrategyReader` — trading's own view of what the live session
has armed, without naming the module that owns the answer.

@details `DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§8: `trading` may not import `modules.strategy.contracts` (a real boot-order
edge already runs the other way — `strategy.dependencies` names `"trading"`
— and the reverse edge is the cycle the Engine's `ExtensionManager` refused
to boot in PR 4.4c). `strategy`'s adapter
(`modules/strategy/adapters/armed_strategy_reader_adapter.py`) implements
this port by wrapping its own, unchanged `IArmedStrategy` and translating
`ArmedStrategySnapshot` at the boundary.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_snapshot import (
    ArmedStrategySnapshot,
)


class IArmedStrategyReader(ABC):
    """The live session's armed state, safe to read from any thread."""

    @abstractmethod
    def armed(self) -> ArmedStrategySnapshot:
        """Both facts at one instant — see `ArmedStrategySnapshot` for why
        they are one call and not two."""
        ...
