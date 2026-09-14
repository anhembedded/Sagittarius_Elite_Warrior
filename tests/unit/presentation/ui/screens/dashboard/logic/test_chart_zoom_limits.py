"""`EPIC-003G2` — `logic/chart_zoom_limits.py`."""

from __future__ import annotations

from typing import Any

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.logic.chart_zoom_limits import (
    DEFAULT_MAX_ZOOM_OUT_CANDLES,
    max_visible_x_range,
)


class FakeConfig:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self._values = values or {}

    def get(self, key: str, default: Any = None, cast: Any = None) -> Any:
        value = self._values.get(key, default)
        return cast(value) if cast is not None and value is not None else value


def test_the_span_is_the_candle_cap_times_one_bar() -> None:
    span = max_visible_x_range(FakeConfig(), TimeFrame.ONE_MINUTE.value)

    assert span == DEFAULT_MAX_ZOOM_OUT_CANDLES * TimeFrame.ONE_MINUTE.to_seconds()


def test_a_slower_timeframe_gets_a_proportionally_wider_span() -> None:
    """The cap is in candles, not in seconds: 2 000 hourly candles must
    span 60× what 2 000 one-minute candles do, or the same zoom gesture
    would show a different number of bars per timeframe."""
    minute = max_visible_x_range(FakeConfig(), TimeFrame.ONE_MINUTE.value)
    hour = max_visible_x_range(FakeConfig(), TimeFrame.ONE_HOUR.value)

    assert hour == minute * 60


def test_the_configured_cap_overrides_the_default() -> None:
    config = FakeConfig({ConfigKeys.CHART_CARD_MAX_ZOOM_OUT_CANDLES.value: 1000})

    span = max_visible_x_range(config, TimeFrame.ONE_MINUTE.value)

    assert span == 1000 * TimeFrame.ONE_MINUTE.to_seconds()
