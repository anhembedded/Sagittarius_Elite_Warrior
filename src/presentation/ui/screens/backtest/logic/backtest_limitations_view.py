from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)

#: BOT-081 — every entry here is true for every run TODAY because the
#: underlying feature simply doesn't exist yet in the engine — there is no
#: live config to branch on. This is the single place that changes when one
#: of those features ships (task's own §5: "mỗi task đó xoá bớt một dòng
#: khỏi danh sách"), rather than a doc/comment scattered across files that
#: nobody remembers to update. Genuinely per-run items (out-of-sample
#: presence, execution mode once BOT-073 ships) are computed in
#: `build_backtest_limitations()` below, not listed here.
#: BOT-105 — the sizing/pyramiding/Short/leverage line that used to sit
#: here was removed: Short (BOT-050), pyramiding + flexible sizing
#: (BOT-104) and leverage (BOT-105) all shipped, so nothing in that claim
#: was still true.
_ALWAYS_APPLICABLE_LIMITATIONS = [
    "Running mode: Static — based on closed candles, not real ticks.",
    "Does not simulate slippage — every order fills at exactly the requested price.",
    "Does not simulate network latency / order processing time.",
    (
        "Does not simulate orderbook depth — orders always fill in full "
        "regardless of size."
    ),
    "No Stop Loss / Take Profit yet.",  # BOT-041
    (
        "Orders fill at the next candle's open price — this blocks lookahead "
        "bias, but introduces an artificial 1-candle delay."
    ),
    (
        'Trading fees can make up most of the result — see "Total Fees Paid" '
        "in the extended metrics."
    ),
]

_NO_OUT_OF_SAMPLE_NOTE = (
    "No out-of-sample validation for this run — the data range is too "
    "short to split 70/30."
)


def build_backtest_limitations(result: BacktestResult) -> list[str]:
    """
    @brief BOT-081: every limitation that applies to THIS specific run —
    read from real per-run state where such state exists, not a static list
    copy-pasted once and left to rot.
    @details `result.out_of_sample` is the one item here with genuine
    per-run state (BOT-080): most ranges get a real in-sample/out-of-sample
    split, but a short enough range still comes back with `out_of_sample is
    None` — that's still worth disclosing for THAT run, even though
    out-of-sample validation exists in the app overall.
    """
    notes = list(_ALWAYS_APPLICABLE_LIMITATIONS)
    if result.out_of_sample is None:
        notes.append(_NO_OUT_OF_SAMPLE_NOTE)
    return notes
