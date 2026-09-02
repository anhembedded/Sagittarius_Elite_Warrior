"""`EPIC-021M` §2.3 — the live equity curve, accumulated in RAM for the
lifetime of the app session. No persistence: a deliberate decision, same
tier as `TradingSessionState` — recorded here so it is not mistaken for an
oversight.
"""

from __future__ import annotations

from collections import deque

from Sagittarius_Elite_Warrior.src.domain.trading.equity_sample import EquitySample

#: A ceiling against unbounded growth over a long-running session, not a
#: chart-rendering concern — unlike `CHART_CARD_MAX_ZOOM_OUT_CANDLES`, this
#: number is never meant to shape what the user sees.
_MAX_SAMPLES = 5000


class EquityCurveRecorder:
    """@brief One instance per app session (DI singleton) — written by
    `FuturesUserDataStream` on every `ACCOUNT_UPDATE`, read by the Trading
    screen's equity chart on construction (backlog) and via
    `EquitySampledEvent` (live).

    @details `deque(maxlen=...)` evicts the oldest sample once full for
    free — no hand-rolled bookkeeping to get wrong (`EPIC-021M` §4's "vượt
    giới hạn số mẫu → bỏ mẫu cũ nhất").
    """

    def __init__(self, max_samples: int = _MAX_SAMPLES) -> None:
        self._samples: deque[EquitySample] = deque(maxlen=max_samples)

    def record(self, sample: EquitySample) -> None:
        self._samples.append(sample)

    @property
    def samples(self) -> list[EquitySample]:
        return list(self._samples)
