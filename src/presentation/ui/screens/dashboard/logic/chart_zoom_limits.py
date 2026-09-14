"""`EPIC-003G2` — how far a Dev Board chart card may zoom out.

@details One line of arithmetic, but it was written out twice inside
`DashboardPresenter` (`_ensure_chart_cards` and `_on_timeframe_changed`),
each copy carrying its own function-local import of `ConfigKeys` and
`TimeFrame` — which `code-quality-rule.md` forbids outright — and its own
inline `2000`.

Two copies of "what the cap is" is how one of them ends up not being
updated: the cards built at startup and the cards re-ranged after a
timeframe click would then disagree about how far the user may zoom out,
on the same screen, with nothing to notice it.
"""

from __future__ import annotations

from typing import Any

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame

#: Candles visible at maximum zoom-out. Beyond this the card stops being a
#: chart and starts being a smear, and the pan cost stops being bounded.
DEFAULT_MAX_ZOOM_OUT_CANDLES = 2000


def max_visible_x_range(config: Any, interval: str) -> float:
    """Widest X span (in seconds) a chart card on `interval` may show.

    @param config The shared `IConfig`; `CHART_CARD_MAX_ZOOM_OUT_CANDLES`
    overrides the default candle count.
    @param interval A `TimeFrame` value such as `"1m"`.
    """
    max_candles = config.get(
        ConfigKeys.CHART_CARD_MAX_ZOOM_OUT_CANDLES.value,
        DEFAULT_MAX_ZOOM_OUT_CANDLES,
        cast=int,
    )
    return max_candles * TimeFrame(interval).to_seconds()
