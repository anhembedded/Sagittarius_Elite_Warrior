from enum import Enum


class ExitReason(str, Enum):
    """
    @brief Why `PaperExchange` closed (or partially closed) a position,
    attached to every `Trade`.
    @details All 5 original members were declared up front (`BOT-045`)
    "so `Trade`'s `exit_reason` type must not change shape again" once
    `BOT-041`/`BOT-049` started producing the other 3 — that promise was
    already broken once those landed, and `BOT-105A` (Trailing Stop,
    Break-Even Stop, Partial Take-Profit) breaks it again the same way:
    new dynamic exit mechanisms need their own reasons so a `Trade`'s
    origin stays truthful (`TRAILING_STOP`/`BREAK_EVEN_STOP` only ever
    replace what would otherwise have been `STOP_LOSS` — `PaperExchange`
    tracks which mechanism last moved a position's stop and reports that,
    never a plain `STOP_LOSS` once either has fired).
    """

    STRATEGY_SIGNAL = "strategy_signal"
    END_OF_BACKTEST = "end_of_backtest"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    LIQUIDATION = "liquidation"
    #: BOT-105A — the stop had ratcheted to break-even (entry price) before
    #: price fell back through it.
    BREAK_EVEN_STOP = "break_even_stop"
    #: BOT-105A — the stop had trailed a new favorable peak before price
    #: pulled back through it.
    TRAILING_STOP = "trailing_stop"
    #: BOT-105A — a configured `tp_levels` price level was reached; the
    #: position stays open at reduced size (see `Trade.quantity`, which is
    #: only the closed slice, not the position's full size).
    PARTIAL_TAKE_PROFIT = "partial_take_profit"
