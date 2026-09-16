from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies import (
    BaseStrategy,
)


class StrategyRegistry:
    """
    @brief Maps a stable key to a strategy class, so backtest/live callers can
    build one on demand.

    @details
    Mirrors `IndicatorScriptRegistry`'s shape for the same reasons:
    registration is explicit (from `BinanceBotModule.register()`), not a
    filesystem scan, so what's installed is greppable and reviewable; the
    trade-off (writing a strategy but forgetting to register it) is covered
    by a guard test instead. No Protocol/interface — one implementation,
    nothing swaps it out, and `EPIC-025` PR 2.1c measured that an
    `IStrategyCatalog` over it would have had **no** consumer it could serve:
    every caller that reads the keys also needs the strategy *classes*, which a
    published contract must not carry. `EPIC-025C` §5 has the measurement and
    the pull request that revisits it.
    """

    def __init__(self) -> None:
        self._strategies: dict[str, type[BaseStrategy]] = {}

    def register(self, key: str, strategy_cls: type[BaseStrategy]) -> None:
        """
        @raises ValueError if the key is already taken — silently overwriting
        would make two strategies fight over one key depending on import order.
        """
        if key in self._strategies:
            raise ValueError(
                f"Strategy key {key!r} is already registered to "
                f"{self._strategies[key].__name__}"
            )
        self._strategies[key] = strategy_cls

    def create(self, key: str, params: Mapping[str, Any] | None = None) -> BaseStrategy:
        """
        @brief Builds a fresh strategy instance.
        @param params Values for the parameters the strategy declares via
        `input_*()` in setup() (BOT-046). None uses every declared default.
        @details Always a new instance — a strategy tracks cross-detection
        state in its own `Series`, so a fresh run needs a fresh object.
        """
        strategy_cls = self._strategies.get(key)
        if strategy_cls is None:
            raise KeyError(f"No strategy registered under key {key!r}")
        return strategy_cls(params)

    def available(self) -> Mapping[str, type[BaseStrategy]]:
        """Returns a copy, so a caller iterating this can't mutate the registry."""
        return dict(self._strategies)
