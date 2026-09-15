"""`EPIC-021M` §2.3 — the live equity curve, accumulated in RAM for the
lifetime of the app session. No persistence: a deliberate decision, same
tier as `TradingSessionState` — recorded here so it is not mistaken for an
oversight.
"""

from __future__ import annotations

from collections import deque

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.equity_sample import (
    EquitySample,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_equity_curve import (
    IEquityCurve,
)

#: A ceiling against unbounded growth over a long-running session, not a
#: chart-rendering concern — unlike `CHART_CARD_MAX_ZOOM_OUT_CANDLES`, this
#: number is never meant to shape what the user sees.
_MAX_SAMPLES = 5000


class EquityCurveRecorder(IEquityCurve):
    """@brief One instance per app session (DI singleton) — written by
    `FuturesUserDataStream` on every `ACCOUNT_UPDATE`, read by the Trading
    screen's equity chart on construction (backlog) and via
    `EquitySampledEvent` (live).

    @details Implements `IEquityCurve`, which is what the two screens hold;
    `record()` is deliberately not on that port — see its docstring.
    `deque(maxlen=...)` evicts the oldest sample once full for
    free — no hand-rolled bookkeeping to get wrong (`EPIC-021M` §4's "vượt
    giới hạn số mẫu → bỏ mẫu cũ nhất").
    """

    def __init__(self, max_samples: int = _MAX_SAMPLES) -> None:
        self._samples: deque[EquitySample] = deque(maxlen=max_samples)

    def record(self, sample: EquitySample) -> None:
        self._samples.append(sample)

    def samples(self) -> tuple[EquitySample, ...]:
        """`IEquityCurve.samples()`. A tuple rather than the list copy this
        used to be: the copy existed only so a caller could not edit the
        `deque` through the returned list, and an immutable answer says that
        instead of defending against it (`EPIC-025` PR 1.3c-3)."""
        return tuple(self._samples)
