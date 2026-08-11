from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade


@dataclass(frozen=True)
class BacktestMetrics:
    """
    @brief Aggregate performance metrics for one backtest run — the 13 rows
    that mirror the core of TradingView's Strategy Tester "Performance
    Summary" tab, which is what a real cross-check against TradingView
    (mandatory before Phase 1 is considered done) will be compared against.
    """

    net_profit: float
    net_profit_percent: float
    gross_profit: float
    gross_loss: float
    max_drawdown_percent: float
    total_closed_trades: int
    percent_profitable: float
    profit_factor: float
    avg_trade: float
    avg_winning_trade: float
    avg_losing_trade: float
    largest_winning_trade: float
    largest_losing_trade: float

    @classmethod
    def compute(
        cls,
        trades: list[Trade],
        equity_curve: list[tuple[datetime, float]],
        initial_balance: float,
    ) -> BacktestMetrics:
        max_drawdown_percent = _max_drawdown_percent(equity_curve)

        if not trades:
            return cls(
                net_profit=0.0,
                net_profit_percent=0.0,
                gross_profit=0.0,
                gross_loss=0.0,
                max_drawdown_percent=max_drawdown_percent,
                total_closed_trades=0,
                percent_profitable=0.0,
                profit_factor=0.0,
                avg_trade=0.0,
                avg_winning_trade=0.0,
                avg_losing_trade=0.0,
                largest_winning_trade=0.0,
                largest_losing_trade=0.0,
            )

        # Breakeven trades (pnl == 0) count toward total_closed_trades but
        # are neither a winner nor a loser — matches TradingView's Percent
        # Profitable definition (winners / total closed trades).
        winners = [t for t in trades if t.pnl > 0]
        losers = [t for t in trades if t.pnl < 0]
        gross_profit = sum(t.pnl for t in winners)
        gross_loss = sum(t.pnl for t in losers)  # <= 0
        net_profit = gross_profit + gross_loss
        total_closed_trades = len(trades)

        if gross_loss != 0:
            profit_factor = gross_profit / abs(gross_loss)
        else:
            profit_factor = float("inf") if gross_profit > 0 else 0.0

        return cls(
            net_profit=net_profit,
            net_profit_percent=(net_profit / initial_balance * 100)
            if initial_balance
            else 0.0,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            max_drawdown_percent=max_drawdown_percent,
            total_closed_trades=total_closed_trades,
            percent_profitable=len(winners) / total_closed_trades * 100,
            profit_factor=profit_factor,
            avg_trade=net_profit / total_closed_trades,
            avg_winning_trade=(gross_profit / len(winners)) if winners else 0.0,
            avg_losing_trade=(gross_loss / len(losers)) if losers else 0.0,
            largest_winning_trade=max((t.pnl for t in winners), default=0.0),
            largest_losing_trade=min((t.pnl for t in losers), default=0.0),
        )


def _max_drawdown_percent(equity_curve: list[tuple[datetime, float]]) -> float:
    """Largest peak-to-trough drop in equity, as a percent of the peak."""
    peak: float | None = None
    max_drawdown = 0.0
    for _, equity in equity_curve:
        if peak is None or equity > peak:
            peak = equity
        if peak:
            drawdown = (peak - equity) / peak * 100
            max_drawdown = max(max_drawdown, drawdown)
    return max_drawdown
