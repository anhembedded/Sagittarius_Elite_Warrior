from __future__ import annotations

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData

#: BOT-080 — chosen by the user over 80/20 or a user-entered ratio (the
#: latter would let someone dial the split until the numbers look good,
#: defeating the point of this check). Not configurable on purpose.
DEFAULT_IN_SAMPLE_RATIO = 0.7


def split_klines_for_out_of_sample(
    klines: list[MarketData],
    in_sample_ratio: float = DEFAULT_IN_SAMPLE_RATIO,
) -> tuple[list[MarketData], list[MarketData]]:
    """
    @brief Splits a chronological kline list into an in-sample prefix and an
    out-of-sample suffix — BOT-080's "Mức 1" (simple split, not
    walk-forward). `klines` must already be in chronological order (the
    order `IMarketDataRepository.get_klines` returns).
    @details A plain count-based split, not time-based — matches the task's
    own framing ("chia khoảng backtest thành 2 phần"). Either side can come
    back empty (e.g. very short ranges) — the caller decides whether an
    empty out-of-sample side means "skip validation" rather than treating it
    as an error.
    """
    split_index = round(len(klines) * in_sample_ratio)
    return klines[:split_index], klines[split_index:]
