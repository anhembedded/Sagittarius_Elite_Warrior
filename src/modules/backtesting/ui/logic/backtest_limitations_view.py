from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_market import (
    market_label,
)

#: BOT-081 — every entry here is true for every run TODAY because the
#: underlying feature simply doesn't exist yet in the engine. This is the
#: single place that changes when one of those features ships (task's own §5:
#: "mỗi task đó xoá bớt một dòng khỏi danh sách"). Genuinely per-run items
#: (running mode, market, exchange filters, out-of-sample presence) are
#: computed in `build_backtest_limitations()` below, not listed here.
#: BOT-105 — the sizing/pyramiding/Short/leverage line was removed once all
#: of them shipped. EPIC-027D — three more were no longer true and are gone:
#: slippage is simulated (a fixed number of ticks), Stop Loss / Take Profit
#: exist (BOT-041, BOT-105A/C), and "Static" is only one of two running modes.
_ALWAYS_APPLICABLE_LIMITATIONS = [
    (
        "Slippage is a fixed number of ticks per fill (Order Execution "
        "settings), not a model of the orderbook."
    ),
    "Does not simulate network latency / order processing time.",
    (
        "Does not simulate orderbook depth — orders always fill in full "
        "regardless of size."
    ),
    (
        'Trading fees can make up most of the result — see "Total Fees Paid" '
        "in the extended metrics."
    ),
]

_STATIC_MODE_NOTE = (
    "Running mode: Static — based on closed candles. Orders fill at the next "
    "candle's open price: this blocks lookahead bias, but introduces an "
    "artificial 1-candle delay."
)
_TICK_MODE_NOTE = (
    "Running mode: Tick replay — bars are rebuilt from stored ticks; a gap in "
    "the ticks is a gap in the bars."
)
_MARKET_NOTES: dict[MarketType, str] = {
    MarketType.SPOT: (
        "Market: {label} — long-only at 1×, never liquidated; short and cover "
        "signals are ignored ({ignored} this run)."
    ),
    MarketType.FUTURES_USD_M: (
        "Market: {label} — isolated margin with no maintenance-margin tiers "
        "and no funding payments."
    ),
}
_FILTERS_APPLIED_NOTE = (
    "Exchange filters applied: quantity step {step}, minimum notional "
    "{min_notional}, tick {tick}."
)
_NO_FILTERS_NOTE = (
    "No exchange filters applied — no exchange metadata was available for "
    "this symbol, so quantities are unrounded and no entry was refused."
)
_NO_OUT_OF_SAMPLE_NOTE = (
    "No out-of-sample validation for this run — the data range is too "
    "short to split 70/30."
)


def build_backtest_limitations(result: BacktestResult) -> list[str]:
    """
    @brief BOT-081: every limitation that applies to THIS specific run —
    read from real per-run state where such state exists, not a static list
    copy-pasted once and left to rot.
    @details Per-run facts, all read off the result: the running mode (only
    the tick engine returns `committed_bars`), the market it simulated and
    the short signals it ignored (EPIC-027D), whether exchange filters
    applied and with which values (EPIC-027C), and whether the range was long
    enough for an out-of-sample split (BOT-080).
    """
    notes = [
        _TICK_MODE_NOTE if result.committed_bars is not None else _STATIC_MODE_NOTE
    ]
    notes.append(
        _MARKET_NOTES[result.market_type].format(
            label=market_label(result.market_type),
            ignored=result.ignored_short_signals,
        )
    )
    filters = result.exchange_filters
    if filters is None:
        notes.append(_NO_FILTERS_NOTE)
    else:
        notes.append(
            _FILTERS_APPLIED_NOTE.format(
                step=f"{filters.step_size:g}",
                min_notional=f"{filters.min_notional:g}",
                tick=f"{filters.tick_size:g}",
            )
        )
    notes.extend(_ALWAYS_APPLICABLE_LIMITATIONS)
    if result.out_of_sample is None:
        notes.append(_NO_OUT_OF_SAMPLE_NOTE)
    return notes
