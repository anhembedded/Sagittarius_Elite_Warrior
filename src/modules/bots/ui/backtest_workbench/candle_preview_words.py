"""`BOT-233` — what the page says about the stored candles of the period, from what the preview knows.

One pure function, so the chart's sentence and the line under the commands cannot disagree, and no text
outlives the state that wrote it (`pitfalls/ui.md` §4).
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_stored_candles import (
    StoredCandles,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench import (
    workbench_words as words,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.candle_window import (
    FINE_KLINES_MAX_PERIOD,
    CandleWindow,
)


@dataclass(frozen=True, slots=True)
class PreviewText:
    """`chart` replaces the plot while there are no candles to draw; `line` is said under the commands."""

    chart: str
    line: str


def preview_text(
    window: CandleWindow | None, found: StoredCandles | None, *, loading: bool
) -> PreviewText:
    if window is None:
        return PreviewText(words.PICK_A_BOT, "")
    if loading:
        return PreviewText(words.LOADING_CANDLES, words.LOADING_CANDLES)
    if found is None:
        return PreviewText(words.CANDLES_UNREAD, words.CANDLES_UNREAD)
    return _stored_text(window, found)


def _stored_text(window: CandleWindow, found: StoredCandles) -> PreviewText:
    interval = window.interval.value
    if found.too_many:
        said = words.too_many_candles(found.expected, interval, found.limit)
        return PreviewText(said, said)
    if found.expected == 0:
        return PreviewText(words.NO_WHOLE_CANDLE, words.NO_WHOLE_CANDLE)
    if found.stored == 0:
        said = words.no_candles(window.symbol, interval)
        return PreviewText(said, said)
    line = (
        words.candles_missing(found.stored, found.expected, interval)
        if found.missing > 0
        else words.all_candles_stored(found.expected, interval)
    )
    if not window.has_fine_klines_synced:
        line = f"{line} {words.coarse_replay(FINE_KLINES_MAX_PERIOD.days)}"
    return PreviewText("", line)
