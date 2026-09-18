"""`ArmedStrategySnapshot` — trading's own copy of `ArmedStrategySnapshot`'s
shape, built from `ArmedStrategyConfig` instead of `LiveStrategyConfig`.

@details `DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§8: same reasoning as `armed_strategy_config.py` in this package — `strategy`'s
adapter (`modules/strategy/adapters/`) builds one of these from its own
`ArmedStrategySnapshot` at the boundary, field for field.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)


@dataclass(frozen=True, slots=True)
class ArmedStrategySnapshot:
    """The armed state of the live session at one instant, as trading reads it."""

    #: What the user armed, or `None` when nothing is armed.
    config: ArmedStrategyConfig | None

    #: Whether an engine is actually built and running for that config.
    engine_running: bool
