from enum import Enum


class ExitReason(str, Enum):
    """
    @brief Why `PaperExchange` closed a position, attached to every `Trade`.
    @details All 5 members are declared up front (`BOT-045`) even though
    only `STRATEGY_SIGNAL`/`END_OF_BACKTEST` are reachable today — `Trade`'s
    `exit_reason` type must not change shape again once `BOT-041` (Stop
    Loss/Take Profit) and `BOT-049` (Liquidation) start producing the other
    3.
    """

    STRATEGY_SIGNAL = "strategy_signal"
    END_OF_BACKTEST = "end_of_backtest"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    LIQUIDATION = "liquidation"
