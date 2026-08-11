from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Generic, TypeVar

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator
from Sagittarius_Elite_Warrior.src.domain.indicators.macd import (
    DEFAULT_MACD_FAST_PERIOD,
    DEFAULT_MACD_SIGNAL_PERIOD,
    DEFAULT_MACD_SLOW_PERIOD,
    MACD,
    MACDValue,
)
from Sagittarius_Elite_Warrior.src.domain.indicators.rsi import DEFAULT_RSI_PERIOD, RSI
from Sagittarius_Elite_Warrior.src.domain.indicators.wma import WMA
from Sagittarius_Elite_Warrior.src.domain.scripting import (
    DEFAULT_HISTORY,
    Series,
    Streak,
    constant_series,
    crossed,
    crossed_above,
    crossed_below,
    is_above,
    is_below,
)

#: Matches IIndicator's own TypeVar style rather than PEP 695 syntax, so the
#: two generic classes in domain/ read the same way.
T = TypeVar("T")


@dataclass(frozen=True)
class PlottedLine:
    """
    @brief One line's value for a single bar, plus how to draw it.
    @details `color` is a plain hex string, never a QColor — this type lives in
    the domain layer and must not depend on any UI toolkit. The presentation
    layer is what turns it into an actual curve.

    Colour is per bar, not per line, so a script can recolour a line as
    conditions change (Pine's `c = b > a ? lime : red`). Whether the chart can
    *render* a mid-line colour change is a presentation concern — the data
    model carries the information either way.
    """

    value: float
    color: str


@dataclass(frozen=True)
class PlottedMarker:
    """
    @brief A one-off shape/label at a point, e.g. a "Buy"/"Sell" tag on a
    crossover bar (Pine's `plotshape`).
    @details Deliberately separate from PlottedLine: markers are sparse events
    on specific bars, whereas lines are continuous series. Nothing is drawn
    automatically — a marker only exists because a script explicitly asked for
    one on that bar.
    """

    value: float
    text: str
    color: str
    #: "up" hangs the label below the point, "down" above it — matching Pine's
    #: shape.labelup / shape.labeldown, which point *at* the price.
    direction: str = "up"


@dataclass(frozen=True)
class PlottedRegion:
    """
    @brief A background tint for the current bar (Pine's `bgcolor`).
    @details One region per bar, not per name — unlike lines, a bar's
    background is a single tint, not several independent series. `opacity`
    (0=invisible, 1=solid) is separate from `color` rather than baked into an
    8-digit hex, because a script is far more likely to vary it deliberately
    (Pine typically uses 85-90% transparency for a trend wash) than to want a
    literal alpha-channel hex code.
    """

    color: str
    opacity: float = 0.15


@dataclass(frozen=True)
class InfoField:
    """
    @brief One row of a script's status panel (Pine's `table.cell`), e.g.
    ("Trend", "UP", color=green).
    @details Only ever shown for the most recently computed bar — a status
    panel reports "where things stand now", not a time series, so there is no
    history to keep. That also removes any need for Pine's `barstate.islast`
    guard: whichever bar was computed last is definitionally the one whose
    info is current.
    """

    label: str
    value: str
    color: str | None = None


class IndicatorHandle(Generic[T]):
    """
    @brief A declared indicator: callable to advance it one bar, and indexable
    to look back at what it produced on previous bars.

    @details Callable so a script body reads like the formula it represents
    (`a1(close)`, not `a1.update(close)`), and indexable (`a1[1]`) because
    cross detection is inherently a two-bar comparison.

    For indicators whose reading is not a plain number (MACD returns a
    MACDValue), history tracking is skipped — `[n]` returns None. Fan the
    reading out into your own Series if you need history on one of its fields.
    """

    def __init__(
        self, indicator: IIndicator[T], history: int = DEFAULT_HISTORY
    ) -> None:
        self._indicator = indicator
        self._series = Series(history)

    def __call__(self, value: float) -> T | None:
        reading = self._indicator.update(value)
        self._series.push(reading if isinstance(reading, (int, float)) else None)
        return reading

    def __getitem__(self, offset: int) -> float | None:
        return self._series[offset]

    @property
    def series(self) -> Series:
        """The underlying Series, for passing to the cross helpers."""
        return self._series


class BaseIndicatorScript(ABC):
    """
    @brief Base for a "study": a named group of one or more chart lines,
    composed from the existing IIndicator primitives (EMA/RSI/MACD).

    @details
    Subclasses declare their building blocks in `setup()` and compute one bar
    at a time in `execute()`, calling `self.plot(...)` per line — deliberately
    mirroring how a TradingView study reads, without inventing a DSL: this is
    a plain Python class and `plot()` is a plain method.

    `plot()` does NOT draw anything. It appends to an in-memory buffer that
    `compute()` drains and returns. That indirection is what keeps this class
    in the domain layer: a script never holds a reference to a chart, a widget,
    or any I/O, so it stays a pure function of (its own state, this candle) and
    can be unit-tested by calling `compute()` and reading the result.

    `compute()` is the framework's entry point and the reason batch replay and
    live ticks can't diverge — both call the exact same method, exactly as
    StrategyEngine._process_one does for strategies.

    Price is available as pre-tracked Series (`self.close`, `self.high`, ...)
    updated before every `execute()`, so crossing *price* works the same way as
    crossing another indicator, and `self.close[1]` is available for free.

    Subclasses set `title` and `overlay` as class attributes:
        overlay=True  -> lines share the candles' price scale
        overlay=False -> lines get their own subplot row (e.g. RSI 0-100)
    """

    #: Human-readable name, shown in the UI's script list.
    title: str = "Untitled Study"

    #: True to draw on the main price plot; False for a dedicated subplot row.
    overlay: bool = True

    #: Bars of lookback kept for every Series this script creates.
    history: int = DEFAULT_HISTORY

    #: How many bars this script needs before its slowest line produces a
    #: real (non-None) value — e.g. an EMA(200) needs 200. Author-declared,
    #: not computed by trial-running the script: a script can compose several
    #: indicators of different periods, so only the author knows the true
    #: figure (BOT-033 — used to decide how much history to fetch, decoupled
    #: from how many bars the chart actually renders).
    min_warmup_bars: int = 0

    #: True if this script should already be enabled the first time its
    #: registry is loaded (BOT-032 Phase 6) — e.g. the built-in EMA 20/50/
    #: 100/200 replacements. Everything else opts in only when the user
    #: checks it (see IndicatorScriptListModel.set_available).
    default_enabled: bool = False

    def __init__(self) -> None:
        self._buffer: dict[str, PlottedLine] = {}
        self._markers: list[PlottedMarker] = []
        self._region: PlottedRegion | None = None
        self._info: dict[str, InfoField] = {}
        self._line_colors: dict[str, str] = {}

        self.open = Series(self.history)
        self.high = Series(self.history)
        self.low = Series(self.history)
        self.close = Series(self.history)
        self.volume = Series(self.history)

        self.setup()

    # ------------------------------------------------------------------ #
    # Declaration helpers — call these from setup()
    # ------------------------------------------------------------------ #

    def ema(self, period: int) -> IndicatorHandle[float]:
        return IndicatorHandle(EMA(period), self.history)

    def wma(self, period: int) -> IndicatorHandle[float]:
        return IndicatorHandle(WMA(period), self.history)

    def rsi(self, period: int = DEFAULT_RSI_PERIOD) -> IndicatorHandle[float]:
        return IndicatorHandle(RSI(period), self.history)

    def macd(
        self,
        fast_period: int = DEFAULT_MACD_FAST_PERIOD,
        slow_period: int = DEFAULT_MACD_SLOW_PERIOD,
        signal_period: int = DEFAULT_MACD_SIGNAL_PERIOD,
    ) -> IndicatorHandle[MACDValue]:
        return IndicatorHandle(
            MACD(fast_period, slow_period, signal_period), self.history
        )

    def series(self) -> Series:
        """
        @brief A hand-fed Series, for any derived value that needs history.
        @details Indicator handles track themselves, but a value a script
        computes itself (`spread = fast - slow`) has nowhere to live —
        declare a Series in `setup()` and `push()` to it in `execute()` to make
        `spread[1]` work like any other series.
        """
        return Series(self.history)

    def level(self, value: float) -> Series:
        """A constant line (RSI 70, MACD zero) usable as a cross operand."""
        return constant_series(value, self.history)

    def streak(self) -> Streak:
        """A consecutive-bars-true counter — see Streak's own docstring."""
        return Streak()

    # ------------------------------------------------------------------ #
    # Comparison helpers — call these from execute().
    # Each accepts IndicatorHandle or Series and is None-safe during warm-up.
    # ------------------------------------------------------------------ #

    @staticmethod
    def _as_series(operand: IndicatorHandle | Series) -> Series:
        return operand.series if isinstance(operand, IndicatorHandle) else operand

    def crossed_above(self, a, b) -> bool:
        """True only on the bar `a` crosses from below `b` to above it."""
        return crossed_above(self._as_series(a), self._as_series(b))

    def crossed_below(self, a, b) -> bool:
        return crossed_below(self._as_series(a), self._as_series(b))

    def crossed(self, a, b) -> bool:
        return crossed(self._as_series(a), self._as_series(b))

    def is_above(self, a, b) -> bool:
        return is_above(self._as_series(a), self._as_series(b))

    def is_below(self, a, b) -> bool:
        return is_below(self._as_series(a), self._as_series(b))

    # ------------------------------------------------------------------ #
    # Output — call from execute()
    # ------------------------------------------------------------------ #

    def plot(self, value: float | None, name: str, color: str) -> None:
        """
        @brief Records one line's value for the current bar.
        @param value None while the underlying indicator is still warming up —
        silently skipped, so scripts never need their own `if is not None`
        guard around every line. Also how Pine's `na` is expressed.
        @details The color is remembered even when `value` is None, so a line's
        color is known from the very first bar — before it has any data. That's
        what lets the chart register the curve up front instead of waiting for
        warm-up to finish.
        """
        self._line_colors[name] = color
        if value is None:
            return
        self._buffer[name] = PlottedLine(value=value, color=color)

    def mark(
        self,
        value: float | None,
        text: str,
        color: str,
        direction: str = "up",
    ) -> None:
        """
        @brief Places a labelled marker on this bar (Pine's `plotshape`).
        @details Only when the script asks — nothing is auto-marked. A None
        value is skipped, so the common `crossed ? price : na` shape is just
        `self.mark(price if crossed else None, ...)`.
        """
        if value is None:
            return
        self._markers.append(
            PlottedMarker(value=value, text=text, color=color, direction=direction)
        )

    def shade(self, color: str | None, opacity: float = 0.15) -> None:
        """
        @brief Tints the chart background for this bar (Pine's `bgcolor`).
        @param color None means no tint this bar — the common
        `condition ? color : na` shape is `self.shade(color if condition else None)`.
        @details Calling this more than once in the same bar simply overwrites
        — a bar has one background, not a stack of them, which is also how
        the last `bgcolor()` call in a Pine script wins on a given bar.
        """
        self._region = None if color is None else PlottedRegion(color, opacity)

    def info(self, label: str, value: object, color: str | None = None) -> None:
        """
        @brief Adds a row to this bar's status panel (Pine's `table.cell`).
        @details Calling this every bar is normal and expected — see
        InfoField's docstring for why there is no `barstate.islast` guard to
        write. Calling it twice with the same `label` in one bar replaces the
        row rather than duplicating it.
        """
        self._info[label] = InfoField(label=label, value=str(value), color=color)

    # ------------------------------------------------------------------ #
    # Framework-facing — script authors do not call these
    # ------------------------------------------------------------------ #

    def compute(self, candle: MarketData) -> Mapping[str, PlottedLine]:
        """
        @brief Runs one bar and returns the lines it produced.
        @returns Only the lines that had a value this bar — empty while every
        building block is still warming up.
        @details Clearing the buffers first is what stops a warmed-up line from
        leaking a stale value into a later bar where it produced nothing.
        Price series are pushed before `execute()` so `self.close[0]` is this
        bar and `self.close[1]` the previous one, matching Pine.
        """
        self._buffer = {}
        self._markers = []
        self._region = None
        self._info = {}

        self.open.push(candle.open_price)
        self.high.push(candle.high_price)
        self.low.push(candle.low_price)
        self.close.push(candle.close_price)
        self.volume.push(candle.volume)

        self.execute(candle)
        return dict(self._buffer)

    def drain_markers(self) -> list[PlottedMarker]:
        """Markers produced by the most recent `compute()`. Separate call so
        adding markers didn't change `compute()`'s established return type."""
        return list(self._markers)

    def drain_region(self) -> PlottedRegion | None:
        """This bar's background tint, or None for no tint."""
        return self._region

    def drain_info(self) -> list[InfoField]:
        """This bar's status panel rows, in the order `info()` was called."""
        return list(self._info.values())

    def line_colors(self) -> Mapping[str, str]:
        """
        @brief Every line color seen so far, keyed by line name.
        @details Populated by `plot()`, so this is empty until the first
        `compute()` call and complete immediately after it (colors are recorded
        regardless of warm-up).
        """
        return dict(self._line_colors)

    # ------------------------------------------------------------------ #
    # Contract for subclasses
    # ------------------------------------------------------------------ #

    @abstractmethod
    def setup(self) -> None:
        """
        @brief Declare this study's building blocks. Runs once, from __init__.
        @details Assign handles to attributes here (`self.a1 = self.ema(20)`)
        so `execute()` can call them per bar.
        """

    @abstractmethod
    def execute(self, candle: MarketData) -> None:
        """
        @brief Compute one bar. Call `self.plot(...)` for every line to draw.
        @param candle The whole MarketData, not just the close price, so a
        script can use high/low/volume without this contract having to change.
        """
