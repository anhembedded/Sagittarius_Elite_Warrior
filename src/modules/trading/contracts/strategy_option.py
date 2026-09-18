"""`StrategyOption` — trading's own copy of one entry in a strategy picker.

@details `IStrategyCatalogReader.options()`'s return type; see
`armed_strategy_config.py` in this package for why trading owns a mirror
rather than importing `modules.strategy.contracts.strategy_option`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StrategyOption:
    """One strategy a catalog offers, as a picker would show it."""

    key: str
    label: str
