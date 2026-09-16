"""`IStrategyEngineFactory`'s implementation (`EPIC-025` PR 3.1b).

**A holder, not a new mechanism.** `build_engine()` in `strategy_factory.py` has
built engines since `BOT-020` and keeps doing the building; this class holds the
two collaborators its consumers used to pass in by hand — the registry and the
publisher — so that naming a strategy key is the whole of what a consumer does.

That is the point of the port rather than a side effect. Before it, both backtest
handlers took `StrategyRegistry` in their constructors and handed it back to
`build_engine()` together with their own `IEventPublisher`: a consumer assembling
another context's collaborators, and the reason
`application.use_cases.backtest.*.handler -> modules.strategy.application.services.*`
sat on the boundary allowlist in six lines.

@par Why it does not wrap the registry's `KeyError`
A mistyped strategy key should come back as the key. Wrapping it would make every
consumer learn a second exception type to say the same thing, and the port's
docstring promises the registry's own error deliberately.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_factory import (
    build_engine,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_engine import (
    IStrategyEngine,
    IStrategyEngineFactory,
)


class StrategyEngineFactory(IStrategyEngineFactory):
    """Builds engines from this module's registry, onto this app's bus."""

    def __init__(
        self, registry: StrategyRegistry, event_publisher: IEventPublisher
    ) -> None:
        self._registry = registry
        self._event_publisher = event_publisher

    def build(
        self, strategy_key: str, params: Mapping[str, Any] | None = None
    ) -> IStrategyEngine:
        return build_engine(
            self._registry, strategy_key, self._event_publisher, params=params
        )
