from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)


@dataclass(frozen=True)
class Signal:
    """
    @brief A strategy's decision at a single point in time.
    @details `price`/`time` should always be derived from the triggering
    candle, never wall-clock — otherwise a batch replay and a live run of
    the same strategy over the same data could disagree.
    """

    symbol: str
    action: SignalAction
    reason: str
    price: float
    time: datetime
    #: Strategy-specific metrics ("QML Signal Score: 92") with no fixed
    #: schema — defaults to empty so every existing `Signal(...)` call site
    #: (including `tests/unit/application/services/test_strategy_engine.py`,
    #: which must stay a 0-diff invariant per `BOT-026`) keeps working
    #: unchanged.
    metadata: Mapping[str, Any] = field(default_factory=dict)
