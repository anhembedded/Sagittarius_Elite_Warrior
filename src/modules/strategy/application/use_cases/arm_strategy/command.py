"""`EPIC-022B` — "run this strategy, with these values, on this market"."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)


@dataclass(frozen=True)
class ArmStrategyCommand:
    """@brief Command to make `config` the live strategy (`EPIC-022A`).

    @details Carries the whole `LiveStrategyConfig` rather than six loose
    fields: the value object is what gets validated, armed, persisted and
    restored, so flattening it here would only mean re-assembling it in
    the handler and giving two places the chance to assemble it
    differently.
    """

    config: LiveStrategyConfig
