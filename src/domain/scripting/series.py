from __future__ import annotations

from collections import deque
from collections.abc import Iterable

#: How many bars of history a Series keeps. Enough for the lookbacks real
#: scripts use (crossovers need 2; a few formulas compare against 3-5 bars
#: back) without letting memory grow with the length of a backtest — Pine
#: keeps everything, we deliberately don't.
DEFAULT_HISTORY = 16


class _NoProvisional:
    """Sentinel type: distinguishes "no tick has poked a provisional value
    for this bar yet" from "a tick explicitly poked None" (a legitimate
    provisional reading, e.g. an indicator still warming up mid-bar) — plain
    `None`, or a bare `object()`, can't carry that distinction precisely in
    a type hint (BOT-042C)."""

    __slots__ = ()


_NO_PROVISIONAL = _NoProvisional()


class Series:
    """
    @brief A value tracked across bars, indexable the way Pine Script indexes:
    `s[0]` is this bar, `s[1]` the previous bar, and so on.

    @details
    This is what makes cross detection expressible at all — "crossed above"
    is inherently a two-bar question (`a[0] > b[0] and a[1] < b[1]`) and a
    script that could only see the current bar could never answer it.

    Reading past the end of recorded history returns None rather than raising:
    on the first bars of a run there genuinely is no previous value, and that
    is the same "not ready yet" state an indicator reports during warm-up, so
    callers already have to handle it.
    """

    def __init__(self, history: int = DEFAULT_HISTORY) -> None:
        if history < 2:
            raise ValueError(
                f"history must be at least 2 to compare bars, got {history}"
            )
        #: Newest first, so index 0 is always the current bar.
        self._values: deque[float | None] = deque(maxlen=history)
        #: Tentative value for the bar still forming — separate from
        #: `_values` so a tick never occupies a history slot on its own.
        self._provisional: float | None | _NoProvisional = _NO_PROVISIONAL

    def push(self, value: float | None) -> float | None:
        """Records this bar's value, committing it permanently. None means
        "no value this bar" (warming up, or a deliberately skipped bar) and
        still occupies a slot, so the bar alignment of `[1]`, `[2]` ... stays
        correct. Clears any pending provisional value for the bar that just
        closed — the next `poke_provisional()` starts the next bar fresh."""
        self._provisional = _NO_PROVISIONAL
        self._values.appendleft(value)
        return value

    def poke_provisional(self, value: float | None) -> float | None:
        """Tentative value for the bar still forming (BOT-042C) — overwrites
        itself on every call within the same bar, never occupies a new
        history slot. `[0]` reads this while set; `[1]`, `[2]`... shift to
        read what would otherwise be `[0]`, `[1]`... i.e. the already-closed
        bars, unaffected by how many times this was called. Cleared by the
        next `push()`."""
        self._provisional = value
        return value

    def __getitem__(self, offset: int) -> float | None:
        if offset < 0:
            raise IndexError(f"Series offset must be >= 0, got {offset}")
        if self._provisional is not _NO_PROVISIONAL:
            if offset == 0:
                return self._provisional  # type: ignore[return-value]
            offset -= 1
        if offset >= len(self._values):
            return None
        return self._values[offset]

    def __len__(self) -> int:
        return len(self._values)

    @property
    def current(self) -> float | None:
        return self[0]

    @property
    def previous(self) -> float | None:
        return self[1]


def _pair(a: Series, b: Series) -> tuple[float, float, float, float] | None:
    """Both series' current and previous values, or None if any is missing —
    the single warm-up guard every cross helper needs."""
    values = (a[0], b[0], a[1], b[1])
    if any(value is None for value in values):
        return None
    return values  # type: ignore[return-value]


def crossed_above(a: Series, b: Series) -> bool:
    """
    @brief True only on the bar where `a` crosses from below `b` to above it.
    @details Pine's `crossover(a, b)` — equivalent to
    `a > b and a[1] < b[1]`. False (not an error) while either series is still
    warming up, so a script never has to guard the call.
    """
    values = _pair(a, b)
    if values is None:
        return False
    a_now, b_now, a_prev, b_prev = values
    return a_prev < b_prev and a_now > b_now


def crossed_below(a: Series, b: Series) -> bool:
    """Pine's `crossunder(a, b)` — `a < b and a[1] > b[1]`."""
    values = _pair(a, b)
    if values is None:
        return False
    a_now, b_now, a_prev, b_prev = values
    return a_prev > b_prev and a_now < b_now


def crossed(a: Series, b: Series) -> bool:
    """Pine's `cross(a, b)` — crossed in either direction."""
    return crossed_above(a, b) or crossed_below(a, b)


def is_above(a: Series, b: Series) -> bool:
    """
    @brief None-safe `a > b` for the current bar.
    @details The plain operator raises TypeError when either side is still
    None during warm-up, which is exactly when a script is most likely to be
    comparing things — hence a helper rather than leaving it to callers.
    """
    return a[0] is not None and b[0] is not None and a[0] > b[0]


def is_below(a: Series, b: Series) -> bool:
    """None-safe `a < b` for the current bar."""
    return a[0] is not None and b[0] is not None and a[0] < b[0]


def constant_series(value: float, history: int = DEFAULT_HISTORY) -> Series:
    """
    @brief A Series holding one fixed number on every bar.
    @details Lets a level be crossed like any other line —
    `crossed_above(rsi, constant_series(70))` — instead of needing a second
    set of scalar-vs-series helpers.
    """
    series = Series(history)
    for _ in range(history):
        series.push(value)
    return series


def series_of(values: Iterable[float | None], history: int = DEFAULT_HISTORY) -> Series:
    """Builds a Series from an oldest-first sequence. Test helper, and handy
    for feeding a precomputed column into a cross check."""
    series = Series(history)
    for value in values:
        series.push(value)
    return series
