from __future__ import annotations

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)

#: BOT-022 deliberately shows the raw result as plain text (no polished
#: cards yet — that's BOT-055/BOT-056/BOT-057) so the end-to-end path
#: (config -> dispatch -> BacktestResult -> screen) can be verified before
#: investing in presentation. This is the one place that formatting lives,
#: so the 3 follow-up tasks have a single spot to delete once they replace it.
_RESULT_TEMPLATE = (
    "Symbol: {symbol}\n"
    "Initial balance: {initial_balance:,.2f}\n"
    "Final balance: {final_balance:,.2f}\n"
    "\n"
    "Net profit: {net_profit:,.2f} ({net_profit_percent:+.2f}%)\n"
    "Gross profit / loss: {gross_profit:,.2f} / {gross_loss:,.2f}\n"
    "Max drawdown: {max_drawdown_percent:.2f}%\n"
    "Closed trades: {total_closed_trades}\n"
    "Win rate: {percent_profitable:.2f}%\n"
    "Profit factor: {profit_factor:.3f}\n"
    "Avg trade / win / loss: {avg_trade:,.2f} / {avg_winning_trade:,.2f} / {avg_losing_trade:,.2f}\n"
    "Largest win / loss: {largest_winning_trade:,.2f} / {largest_losing_trade:,.2f}"
)


def format_result_summary(result: BacktestResult) -> str:
    """
    @brief Renders a `BacktestResult` as plain text for the temporary raw
    result panel.
    @details Reads every field directly off `result`/`result.metrics` rather
    than summarizing — the point of the raw panel is to let a human verify
    the real domain numbers reached the screen unmodified.
    """
    metrics = result.metrics
    return _RESULT_TEMPLATE.format(
        symbol=result.symbol,
        initial_balance=result.initial_balance,
        final_balance=result.final_balance,
        net_profit=metrics.net_profit,
        net_profit_percent=metrics.net_profit_percent,
        gross_profit=metrics.gross_profit,
        gross_loss=metrics.gross_loss,
        max_drawdown_percent=metrics.max_drawdown_percent,
        total_closed_trades=metrics.total_closed_trades,
        percent_profitable=metrics.percent_profitable,
        profit_factor=metrics.profit_factor,
        avg_trade=metrics.avg_trade,
        avg_winning_trade=metrics.avg_winning_trade,
        avg_losing_trade=metrics.avg_losing_trade,
        largest_winning_trade=metrics.largest_winning_trade,
        largest_losing_trade=metrics.largest_losing_trade,
    )
