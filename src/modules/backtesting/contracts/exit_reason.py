from enum import Enum


class ExitReason(str, Enum):
    """
    @brief Why `PaperExchange` closed a position, attached to every `Trade`.
    @details The original 5 members were declared up front (`BOT-045`) so
    `Trade`'s `exit_reason` type would not have to change shape again as
    producers landed: `STRATEGY_SIGNAL`/`END_OF_BACKTEST` from
    `PaperExchange` itself, `STOP_LOSS`/`TAKE_PROFIT` from
    `OrderMatchingPolicy.evaluate_stop_levels()` since `BOT-041`/`BOT-050`
    (stop-loss wins when one bar touches both), `LIQUIDATION` from
    `MarginRiskPolicy`/`BOT-049`. `PARTIAL_TAKE_PROFIT` (`BOT-105C`) is a
    distinct trading fact from a full `TAKE_PROFIT` close
    (`domain-truth-rule.md`) — its `Trade.quantity` is a fraction of the
    position's entry quantity, never the whole thing, and a metrics
    consumer must be able to tell the two apart.
    """

    STRATEGY_SIGNAL = "strategy_signal"
    END_OF_BACKTEST = "end_of_backtest"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    LIQUIDATION = "liquidation"
    PARTIAL_TAKE_PROFIT = "partial_take_profit"
