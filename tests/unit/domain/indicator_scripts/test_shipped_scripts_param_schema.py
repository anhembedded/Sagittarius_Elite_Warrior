"""
BOT-044 regression guard: adding the `input_*()` mechanism to
BaseIndicatorScript must not change how any *shipped* script behaves.

Every script in the registry today was written before BOT-044 and declares no
parameters, so each must report an empty schema and keep producing exactly the
values it produced before. BOT-048 will convert the fixed-period ones
(ema_20/50/100/200, rsi_14, macd_full) to declare their period as an input —
when that lands, the scripts it converts move out of
`test_every_shipped_script_declares_no_inputs_yet` and gain their own
schema assertions instead. Until then this pins "nothing changed".
"""

from datetime import UTC, datetime, timedelta

import pytest

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import (
    DevIndicatorScript,
    Ema20Script,
    Ema50Script,
    Ema100Script,
    Ema200Script,
    EmaCrossScript,
    EmaRibbonScript,
    MacdFullScript,
    Rsi14Script,
)

#: The nine scripts BinanceBotModule registers today.
SHIPPED_SCRIPTS = [
    Rsi14Script,
    Ema20Script,
    Ema50Script,
    Ema100Script,
    Ema200Script,
    MacdFullScript,
    EmaRibbonScript,
    EmaCrossScript,
    DevIndicatorScript,
]


def _candle(close: float, index: int) -> MarketData:
    open_time = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
    return MarketData(
        symbol="ETHUSDT",
        interval="1m",
        open_time=open_time,
        open_price=close,
        high_price=close + 1,
        low_price=close - 1,
        close_price=close,
        volume=10.0,
        close_time=open_time + timedelta(minutes=1),
        quote_asset_volume=1000.0,
        number_of_trades=5,
        taker_buy_base_asset_volume=5.0,
        taker_buy_quote_asset_volume=500.0,
    )


def _run(script, bar_count: int = 60) -> dict:
    """Feeds a rising-then-falling series and returns the final bar's lines."""
    last: dict = {}
    for index in range(bar_count):
        close = 100.0 + index if index < bar_count // 2 else 100.0 + bar_count - index
        last = script.compute(_candle(close, index))
    return last


@pytest.mark.parametrize("script_cls", SHIPPED_SCRIPTS, ids=lambda c: c.__name__)
def test_every_shipped_script_declares_no_inputs_yet(script_cls):
    assert script_cls().inputs == ()


@pytest.mark.parametrize("script_cls", SHIPPED_SCRIPTS, ids=lambda c: c.__name__)
def test_every_shipped_script_constructs_with_explicit_empty_params(script_cls):
    """`create(key)` and `create(key, {})` must be interchangeable — an empty
    mapping is not the same object as None, and the code path differs."""
    assert script_cls({}).inputs == ()


@pytest.mark.parametrize("script_cls", SHIPPED_SCRIPTS, ids=lambda c: c.__name__)
def test_every_shipped_script_produces_identical_output_with_and_without_params(
    script_cls,
):
    """The real regression check: same inputs, same plotted values, whether
    constructed the old way or through the new params-aware path."""
    without = _run(script_cls())
    with_empty = _run(script_cls({}))

    assert without.keys() == with_empty.keys()
    for name, line in without.items():
        assert line.value == with_empty[name].value, f"line {name!r} changed"


@pytest.mark.parametrize("script_cls", SHIPPED_SCRIPTS, ids=lambda c: c.__name__)
def test_no_shipped_script_silently_accepts_an_undeclared_param(script_cls):
    with pytest.raises(ValueError, match="never declares"):
        script_cls({"period": 99})
