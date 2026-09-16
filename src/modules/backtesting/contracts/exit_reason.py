from enum import Enum


class ExitReason(str, Enum):
    """
    @brief Why `PaperExchange` closed a position, attached to every `Trade`.
    @details All 5 members were declared up front (`BOT-045`) so `Trade`'s
    `exit_reason` type would not have to change shape again as producers
    landed. Four of them now have one: `STRATEGY_SIGNAL`/`END_OF_BACKTEST`
    from `PaperExchange` itself, and `STOP_LOSS`/`TAKE_PROFIT` from
    `OrderMatchingPolicy.evaluate_stop_levels()` since `BOT-041`/`BOT-050`
    (stop-loss wins when one bar touches both). `LIQUIDATION` is still
    unreachable — `MarginRiskPolicy` values positions and realizes PnL but
    never force-closes one; `BOT-049` owns that.
    """

    STRATEGY_SIGNAL = "strategy_signal"
    END_OF_BACKTEST = "end_of_backtest"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    LIQUIDATION = "liquidation"
