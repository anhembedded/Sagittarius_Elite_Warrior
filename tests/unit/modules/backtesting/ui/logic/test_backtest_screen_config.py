"""`EPIC-003E3` — `logic/backtest_screen_config.py`.

What a hand-edited `user_config.json` does to this screen used to be three
`try/except` ladders buried in a 272-line `__init__`. These are those
ladders, asserted directly.
"""

from __future__ import annotations

from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_screen_config import (
    DEFAULT_CHART_KLINES_FETCH_LIMIT,
    BacktestScreenConfig,
)
from sagittarius_engine.extensions.pyside_mvc.mvc.base_view import DEV_MODE_CONFIG_KEY

FALLBACK_SYMBOL = "ETHUSDT"
DEFAULT_LOG_MAX_ENTRIES = 500


class FakeConfig:
    """The two methods `read_from` uses, nothing else."""

    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self._values = values or {}

    def get_all(self) -> dict[str, Any]:
        return dict(self._values)

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)


def _read(values: dict[str, Any] | None = None) -> BacktestScreenConfig:
    return BacktestScreenConfig.read_from(
        FakeConfig(values),
        fallback_symbol=FALLBACK_SYMBOL,
        default_log_max_entries=DEFAULT_LOG_MAX_ENTRIES,
    )


def test_an_empty_config_gives_every_shipped_default() -> None:
    config = _read()

    assert config.symbol == FALLBACK_SYMBOL
    assert config.default_interval == ""
    assert config.is_dev_mode is False
    assert config.log_max_entries == DEFAULT_LOG_MAX_ENTRIES
    assert config.chart_klines_fetch_limit == DEFAULT_CHART_KLINES_FETCH_LIMIT
    assert config.chart_opengl_enabled is False
    assert config.chart_cached_interaction_enabled is False


def test_configured_values_win_over_the_defaults() -> None:
    config = _read(
        {
            "DEFAULT_INTERVAL": "4h",
            DEV_MODE_CONFIG_KEY: True,
            ConfigKeys.BACKTEST_LOG_MAX_ENTRIES.value: 42,
            ConfigKeys.BACKTEST_CHART_KLINES_FETCH_LIMIT.value: 1234,
            ConfigKeys.BACKTEST_CHART_OPENGL_ENABLED.value: True,
            ConfigKeys.BACKTEST_CHART_CACHED_INTERACTION_ENABLED.value: True,
        }
    )

    assert config.default_interval == "4h"
    assert config.is_dev_mode is True
    assert config.log_max_entries == 42
    assert config.chart_klines_fetch_limit == 1234
    assert config.chart_opengl_enabled is True
    assert config.chart_cached_interaction_enabled is True


@pytest.mark.parametrize("bad", ["many", "", None, 0, -5, 3.7 * 0])
def test_an_unusable_count_falls_back_instead_of_capping_at_something_odd(
    bad: Any,
) -> None:
    config = _read(
        {
            ConfigKeys.BACKTEST_LOG_MAX_ENTRIES.value: bad,
            ConfigKeys.BACKTEST_CHART_KLINES_FETCH_LIMIT.value: bad,
        }
    )

    assert config.log_max_entries == DEFAULT_LOG_MAX_ENTRIES
    assert config.chart_klines_fetch_limit == DEFAULT_CHART_KLINES_FETCH_LIMIT


def test_true_is_not_a_count_of_one() -> None:
    """`bool` is a subclass of `int`, so `int(True)` is 1. Before this
    module the chart-fetch limit had no such guard: `true` in the config
    would have capped the chart at a single candle, with no error anywhere.
    The log limit did have the guard — one shared helper is what stops that
    from being a per-field accident."""
    config = _read(
        {
            ConfigKeys.BACKTEST_LOG_MAX_ENTRIES.value: True,
            ConfigKeys.BACKTEST_CHART_KLINES_FETCH_LIMIT.value: True,
        }
    )

    assert config.log_max_entries == DEFAULT_LOG_MAX_ENTRIES
    assert config.chart_klines_fetch_limit == DEFAULT_CHART_KLINES_FETCH_LIMIT


def test_an_invalid_interval_is_passed_through_untouched() -> None:
    """Deliberately NOT validated here: `BackTestViewModel` already has a
    default timeframe, and a second opinion about what "default" means is
    how `EPIC-014`'s bug happened (a valid `4h` silently ignored because a
    five-pill toolbar tuple was deciding what a valid config value was).
    The Presenter checks it against the domain's own timeframes."""
    config = _read({"DEFAULT_INTERVAL": "not_a_timeframe"})

    assert config.default_interval == "not_a_timeframe"
