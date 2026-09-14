"""`BOT-125` review — `LiveStrategyConfig` guards its own invariants.

Before this, the only thing stopping a nonsense leverage or an untradeable
interval was a Qt spin box and a combo — widgets that constrain *typing*
and nothing else. The same values also arrive from `app_config.json` at
boot and from a restored session, neither of which passes through a
widget, so a hand-edited `"trading.live_leverage": 0` armed happily and
reached position sizing, and `"trading.live_interval": "1M"` armed a bot
that could never match a tick.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.domain.value_objects.live_strategy_config import (
    MAX_LEVERAGE,
    MAX_SIZING_PERCENT,
    MIN_LEVERAGE,
    MIN_SIZING_PERCENT,
    SUPPORTED_LIVE_INTERVALS,
    LiveStrategyConfig,
)


def _config(**overrides) -> LiveStrategyConfig:
    values = {"strategy_key": "ema_crossover", "symbol": "BTCUSDT", "interval": "1m"}
    values.update(overrides)
    return LiveStrategyConfig(**values)


def test_a_valid_config_constructs() -> None:
    config = _config(sizing_percent=12.5, leverage=3.0)

    assert config.is_complete is True
    assert config.sizing_percent == 12.5


@pytest.mark.parametrize("leverage", [0.0, -1.0, MAX_LEVERAGE + 1])
def test_a_leverage_outside_the_bounds_is_refused(leverage: float) -> None:
    with pytest.raises(ValueError, match="leverage"):
        _config(leverage=leverage)


@pytest.mark.parametrize("percent", [0.0, -5.0, MAX_SIZING_PERCENT + 0.1])
def test_a_sizing_percent_outside_the_bounds_is_refused(percent: float) -> None:
    with pytest.raises(ValueError, match="sizing_percent"):
        _config(sizing_percent=percent)


def test_the_bounds_themselves_are_accepted() -> None:
    """Inclusive bounds — 1x leverage and 100% of equity are both real,
    usable choices, not off-by-one rejections."""
    assert _config(leverage=MIN_LEVERAGE).leverage == MIN_LEVERAGE
    assert _config(leverage=MAX_LEVERAGE).leverage == MAX_LEVERAGE
    assert _config(sizing_percent=MIN_SIZING_PERCENT).sizing_percent == (
        MIN_SIZING_PERCENT
    )
    assert _config(sizing_percent=MAX_SIZING_PERCENT).sizing_percent == (
        MAX_SIZING_PERCENT
    )


@pytest.mark.parametrize(
    "interval", [TimeFrame.ONE_SECOND.value, TimeFrame.ONE_WEEK.value, "1hr"]
)
def test_an_interval_live_trading_does_not_support_is_refused(interval: str) -> None:
    """`1s` and `1w` are real `TimeFrame` members and still refused — the
    subset is a trading-risk decision, not a parsing one — and `1hr` is
    the typo shape the enum-derived constant exists to make impossible."""
    with pytest.raises(ValueError, match="Timeframe"):
        _config(interval=interval)


def test_an_empty_interval_is_incomplete_not_invalid() -> None:
    """A half-filled card must still construct; `is_complete` is what says
    it is not runnable yet. Raising here would make the ViewModel unable
    to hold what the user is part-way through choosing."""
    config = _config(interval="")

    assert config.is_complete is False


def test_every_supported_interval_really_is_a_domain_timeframe() -> None:
    """The constant is built from `TimeFrame` members, so this can only
    fail if someone re-types it as raw strings — which is the drift it was
    introduced to prevent."""
    known = {frame.value for frame in TimeFrame}

    assert set(SUPPORTED_LIVE_INTERVALS) <= known
    assert SUPPORTED_LIVE_INTERVALS, "an empty list would disable live trading"


def test_params_are_snapshotted_not_aliased() -> None:
    """The UI keeps editing its own dict while the user types; an armed
    config that changed underneath the running engine would make "what is
    actually running" unanswerable."""
    editable = {"fast_period": 5}
    config = _config(strategy_params=editable)

    editable["fast_period"] = 999

    assert config.strategy_params["fast_period"] == 5
