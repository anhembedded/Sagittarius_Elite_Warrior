from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    ratio_key,
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

#: BOT-022 deliberately shows the raw result as plain text (no polished
#: cards yet — that's BOT-055/BOT-056/BOT-057) so the end-to-end path
#: (config -> dispatch -> BacktestResult -> screen) can be verified before
#: investing in presentation. This is the one place that arranges it, so the
#: follow-up that replaces it has a single spot to delete. It writes no number
#: itself: every figure goes through `AppValueFormatter` (`EPIC-033N`).
_RESULT_TEMPLATE = (
    "Symbol: {symbol}\n"
    "Initial balance: {initial_balance}\n"
    "Final balance: {final_balance}\n"
    "\n"
    "Net profit: {net_profit} ({net_profit_percent})\n"
    "Gross profit / loss: {gross_profit} / {gross_loss}\n"
    "Max drawdown: {max_drawdown_percent}\n"
    "Closed trades: {total_closed_trades}\n"
    "Win rate: {percent_profitable}\n"
    "Profit factor: {profit_factor}\n"
    "Avg trade / win / loss: {avg_trade} / {avg_winning_trade} / {avg_losing_trade}\n"
    "Largest win / loss: {largest_winning_trade} / {largest_losing_trade}"
)


def _money(value: float) -> str:
    return write_value(ColumnKind.MONEY, value)


def _percent(value: float) -> str:
    return write_value(ColumnKind.PERCENT, value)


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
        initial_balance=_money(result.initial_balance),
        final_balance=_money(result.final_balance),
        net_profit=_money(metrics.net_profit),
        net_profit_percent=_percent(metrics.net_profit_percent),
        gross_profit=_money(metrics.gross_profit),
        gross_loss=_money(metrics.gross_loss),
        max_drawdown_percent=_percent(metrics.max_drawdown_percent),
        total_closed_trades=write_value(
            ColumnKind.QUANTITY, metrics.total_closed_trades
        ),
        percent_profitable=_percent(metrics.percent_profitable),
        profit_factor=write_value(
            ColumnKind.QUANTITY, metrics.profit_factor, ratio_key("profit_factor")
        ),
        avg_trade=_money(metrics.avg_trade),
        avg_winning_trade=_money(metrics.avg_winning_trade),
        avg_losing_trade=_money(metrics.avg_losing_trade),
        largest_winning_trade=_money(metrics.largest_winning_trade),
        largest_losing_trade=_money(metrics.largest_losing_trade),
    )
