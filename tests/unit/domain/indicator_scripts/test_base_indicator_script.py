"""
Tests for BaseIndicatorScript — the contract every custom indicator script
implements (BOT-032 Phase 0).

The class under test is pure domain logic, so these use real scripts and real
EMA/RSI/MACD instances rather than mocks; there is no I/O to stub out.
"""

import pytest

from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.indicator_scripts import BaseIndicatorScript, PlottedLine

_RED = "#e74c3c"
_BLUE = "#3498db"


class _TwoEmaScript(BaseIndicatorScript):
    """Minimal realistic script: two EMAs with different warm-up lengths, so
    tests can observe a bar where one line exists and the other doesn't."""

    title = "Two EMA"
    overlay = True

    def setup(self) -> None:
        self.fast = self.ema(2)
        self.slow = self.ema(5)

    def execute(self, candle: MarketData) -> None:
        close = candle.close_price
        self.plot(self.fast(close), "FAST", color=_RED)
        self.plot(self.slow(close), "SLOW", color=_BLUE)


class _ConditionalScript(BaseIndicatorScript):
    """Plots a line only on alternating bars — used to prove the per-bar buffer
    is cleared rather than carrying a stale value forward."""

    title = "Conditional"
    overlay = False

    def setup(self) -> None:
        self._bar = 0

    def execute(self, candle: MarketData) -> None:
        self._bar += 1
        if self._bar % 2 == 1:
            self.plot(candle.close_price, "ODD_BARS", color=_RED)


# ---------------------------------------------------------------------------
# Warm-up / buffer semantics
# ---------------------------------------------------------------------------


def test_returns_nothing_while_every_line_is_warming_up(make_candle):
    script = _TwoEmaScript()

    assert script.compute(make_candle(100.0)) == {}


def test_a_line_appears_as_soon_as_its_own_indicator_warms_up(make_candle):
    """Lines warm up independently — the faster EMA must not be held back
    waiting for the slower one."""
    script = _TwoEmaScript()

    script.compute(make_candle(100.0, 0))
    second_bar = script.compute(make_candle(102.0, 1))

    assert set(second_bar) == {"FAST"}  # EMA(2) ready, EMA(5) still warming


def test_all_lines_present_once_every_indicator_is_warm(make_candle):
    script = _TwoEmaScript()

    result = {}
    for index, close in enumerate([100.0, 102.0, 101.0, 103.0, 104.0]):
        result = script.compute(make_candle(close, index))

    assert set(result) == {"FAST", "SLOW"}
    assert all(isinstance(line, PlottedLine) for line in result.values())


def test_buffer_is_cleared_between_bars_so_stale_values_never_leak(make_candle):
    """Regression guard for the core risk of the plot()-into-a-buffer design:
    a bar that plots nothing must return nothing, not the previous bar's data."""
    script = _ConditionalScript()

    first = script.compute(make_candle(100.0, 0))
    second = script.compute(make_candle(200.0, 1))
    third = script.compute(make_candle(300.0, 2))

    assert set(first) == {"ODD_BARS"}
    assert second == {}, "bar that plotted nothing leaked the previous bar's value"
    assert third["ODD_BARS"].value == 300.0


def test_compute_returns_a_copy_not_the_live_buffer(make_candle):
    """A caller holding onto one bar's result must not see it mutate when the
    next bar runs — the presenter accumulates these across a whole history."""
    script = _ConditionalScript()

    first = script.compute(make_candle(100.0, 0))
    script.compute(make_candle(200.0, 1))

    assert first["ODD_BARS"].value == 100.0


# ---------------------------------------------------------------------------
# plot() semantics
# ---------------------------------------------------------------------------


def test_plot_records_value_and_color_together(make_candle):
    script = _ConditionalScript()

    line = script.compute(make_candle(123.5, 0))["ODD_BARS"]

    assert line == PlottedLine(value=123.5, color=_RED)


def test_line_colors_are_known_during_warmup_before_any_value_exists(make_candle):
    """The chart registers a curve (name + color) before it has data, so colors
    must survive a bar where plot() was called with None."""
    script = _TwoEmaScript()

    assert script.compute(make_candle(100.0)) == {}  # nothing warm yet
    assert script.line_colors() == {"FAST": _RED, "SLOW": _BLUE}


def test_line_colors_is_empty_before_the_first_bar(make_candle):
    """Colors come from plot() calls, so they genuinely don't exist yet — the
    presenter must not assume it can read them straight after construction."""
    assert _TwoEmaScript().line_colors() == {}


def test_line_colors_returns_a_copy(make_candle):
    script = _TwoEmaScript()
    script.compute(make_candle(100.0))

    script.line_colors()["FAST"] = "#000000"

    assert script.line_colors()["FAST"] == _RED


# ---------------------------------------------------------------------------
# Class contract
# ---------------------------------------------------------------------------


def test_setup_runs_once_at_construction(make_candle):
    """Handles must exist before the first execute() — a script that built its
    indicators lazily per bar would silently reset their warm-up every tick."""
    script = _TwoEmaScript()

    assert hasattr(script, "fast")
    assert hasattr(script, "slow")


def test_subclass_must_implement_setup_and_execute(make_candle):
    class _Incomplete(BaseIndicatorScript):
        pass

    with pytest.raises(TypeError):
        _Incomplete()


def test_declaration_helpers_wrap_indicators_as_callables(make_candle):
    """The ergonomic point of the design: a1(close), not a1.update(close)."""

    class _HelperScript(BaseIndicatorScript):
        def setup(self) -> None:
            self.e = self.ema(2)
            self.r = self.rsi(2)
            self.m = self.macd(2, 3, 2)

        def execute(self, candle: MarketData) -> None:
            pass

    script = _HelperScript()

    assert script.e(10.0) is None  # warming up, but callable and no crash
    assert callable(script.r)
    assert callable(script.m)


def test_two_instances_of_the_same_script_do_not_share_state(make_candle):
    """registry.create() hands out a fresh instance per run precisely because
    indicators have no reset() — prove instances are genuinely independent."""
    first = _TwoEmaScript()
    second = _TwoEmaScript()

    for index, close in enumerate([100.0, 102.0, 101.0, 103.0, 104.0]):
        first.compute(make_candle(close, index))

    assert first.compute(make_candle(105.0, 5)) != {}
    assert second.compute(make_candle(105.0, 5)) == {}
