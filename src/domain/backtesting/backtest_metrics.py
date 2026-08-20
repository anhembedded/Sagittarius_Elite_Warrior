from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise

from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade

#: BOT-106A — Sharpe/Sortino/Calmar annualize a per-bar statistic by
#: scaling with sqrt(periods_per_year)/CAGR's own year fraction.
#: periods_per_year is derived from the equity curve's OWN average bar
#: spacing (365.25 days/year ÷ avg seconds/bar) rather than a passed-in
#: timeframe — BacktestMetrics.compute() already receives every timestamp
#: it needs to derive this itself, so no new parameter/coupling to
#: TimeFrame is needed.
_SECONDS_PER_YEAR = 365.25 * 24 * 3600
#: BOT-106A — a per-bar return series that is mathematically constant (e.g.
#: every bar compounding by the exact same percentage) still comes out of
#: floating-point subtraction as a stdev on the order of 1e-16, not exactly
#: 0.0 — dividing by that produces an absurd, misleading Sharpe/Sortino
#: (observed: ~3.2e15) instead of the intended "no real volatility here"
#: 0.0. `math.isclose(..., abs_tol=_ZERO_VOLATILITY_TOLERANCE)` treats
#: anything below this as zero; per-bar returns in practice are O(1e-3) to
#: O(1e-1), so this is far below any volatility that should ever register.
_ZERO_VOLATILITY_TOLERANCE = 1e-9

#: BOT-079 — if total fees paid exceed this fraction of |net_profit|, the
#: result is flagged as fee-dominated: net_profit alone can read as "this
#: strategy is bad" when it's actually "this strategy is roughly breakeven
#: and fees ate the rest" (see BUG-002: 807 trades, -80.71% net, of which
#: -80.11 points were fees alone). A starting number, not a validated
#: threshold — revisit once this has seen real use.
FEE_DOMINANCE_WARNING_RATIO = 0.3

#: BOT-079 — if the average number of bars between trades drops below this,
#: flag the run as high-frequency: a strategy firing this often is far more
#: exposed to per-trade fees eating any edge it has. Same caveat as above.
MIN_BARS_PER_TRADE_WARNING_THRESHOLD = 15.0


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
    #: BOT-079 — sum of every Trade.fees_paid (entry + exit combined). All
    #: of net_profit/gross_profit/gross_loss/... above are already computed
    #: from Trade.pnl, which is *after* fees (PaperExchange._close()) — this
    #: is the one field that surfaces how much of that result was fees,
    #: which nothing else here does.
    total_fees_paid: float = 0.0
    #: BOT-079 — len(equity_curve) / total_closed_trades. Deliberately
    #: bars, not a wall-clock rate ("trades/day") — that would need to know
    #: the candle interval, which BacktestMetrics has no reason to know;
    #: bar count is already timeframe-independent.
    avg_bars_per_trade: float = 0.0
    #: BOT-079 — see FEE_DOMINANCE_WARNING_RATIO. Informational only: never
    #: blocks a run, never implies the numbers above are wrong.
    has_high_fee_ratio: bool = False
    #: BOT-079 — see MIN_BARS_PER_TRADE_WARNING_THRESHOLD.
    has_high_trade_frequency: bool = False
    #: BOT-106A — mean per-bar return over per-bar volatility, annualized.
    #: Risk-free rate assumed 0 (no risk-free-rate input anywhere in this
    #: codebase to subtract) — matches TradingView's own Sharpe default.
    #: 0.0 (not NaN/Inf) whenever volatility is 0 (fewer than 2 bars, or
    #: every bar had an identical return — e.g. a flat equity curve).
    sharpe_ratio: float = 0.0
    #: BOT-106A — Sharpe's own formula, but volatility is downside
    #: deviation only (negative per-bar returns) instead of total stdev —
    #: a strategy with volatile GAINS and zero losing bars is not
    #: penalized. 0.0 whenever there are no negative bars to measure.
    sortino_ratio: float = 0.0
    #: BOT-106A — CAGR ÷ |max_drawdown_percent| (both already expressed as
    #: percent points, e.g. 25.0 for +25%). 0.0 whenever max_drawdown is 0
    #: (nothing to divide a real drawdown by) or the run spans under a day
    #: (CAGR over a near-zero year-fraction is not a meaningful annual
    #: rate).
    calmar_ratio: float = 0.0
    #: BOT-106A — longest peak-to-recovery stretch, in BARS (not wall-clock
    #: days) — same timeframe-independence reasoning avg_bars_per_trade
    #: already documents above. Counts every bar strictly below the
    #: running peak; a drawdown still open at the end of the run counts
    #: through the last bar (never "recovered" for this run's purposes).
    max_drawdown_duration_bars: int = 0
    #: BOT-106A — longest run of consecutive trades with pnl > 0. A
    #: breakeven trade (pnl == 0) ends the streak without starting a new
    #: one, same treatment TradingView gives a scratch trade.
    max_consecutive_wins: int = 0
    #: BOT-106A — longest run of consecutive trades with pnl < 0.
    max_consecutive_losses: int = 0

    @classmethod
    def compute(
        cls,
        trades: list[Trade],
        equity_curve: list[tuple[datetime, float]],
        initial_balance: float,
    ) -> BacktestMetrics:
        max_drawdown_percent = _max_drawdown_percent(equity_curve)
        max_drawdown_duration_bars = _max_drawdown_duration_bars(equity_curve)
        sharpe_ratio, sortino_ratio = _sharpe_and_sortino(equity_curve)
        calmar_ratio = _calmar_ratio(equity_curve, max_drawdown_percent)

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
                total_fees_paid=0.0,
                avg_bars_per_trade=0.0,
                has_high_fee_ratio=False,
                has_high_trade_frequency=False,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio,
                max_drawdown_duration_bars=max_drawdown_duration_bars,
                max_consecutive_wins=0,
                max_consecutive_losses=0,
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

        total_fees_paid = sum(t.fees_paid for t in trades)
        avg_bars_per_trade = len(equity_curve) / total_closed_trades
        max_consecutive_wins, max_consecutive_losses = _max_consecutive_streaks(trades)

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
            total_fees_paid=total_fees_paid,
            avg_bars_per_trade=avg_bars_per_trade,
            has_high_fee_ratio=total_fees_paid
            > FEE_DOMINANCE_WARNING_RATIO * abs(net_profit),
            has_high_trade_frequency=avg_bars_per_trade
            < MIN_BARS_PER_TRADE_WARNING_THRESHOLD,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown_duration_bars=max_drawdown_duration_bars,
            max_consecutive_wins=max_consecutive_wins,
            max_consecutive_losses=max_consecutive_losses,
        )


def _max_drawdown_percent(equity_curve: list[tuple[datetime, float]]) -> float:
    """Largest peak-to-trough drop in equity, as a percent of the peak."""
    if not equity_curve:
        return 0.0

    # BOT-081: Optimization - avoid calling max() and doing math on every
    # single bar. By tracking the peak and only computing drawdown when
    # equity is below the peak, we skip operations on new highs. Inlining
    # the max_drawdown > check saves significant overhead in tight loops.
    peak = equity_curve[0][1]
    max_drawdown = 0.0

    for _, equity in equity_curve:
        if equity > peak:
            peak = equity
        elif peak:  # Guard against DivisionByZero if starting equity was 0
            drawdown = (peak - equity) / peak * 100
            max_drawdown = max(max_drawdown, drawdown)

    return max_drawdown


def _bar_returns(equity_curve: list[tuple[datetime, float]]) -> list[float]:
    """Percent-of-prior-bar return between each consecutive `equity_curve`
    point — the per-bar return series Sharpe/Sortino are computed over."""
    returns: list[float] = []
    for (_, prev_equity), (_, curr_equity) in pairwise(equity_curve):
        if prev_equity:
            returns.append((curr_equity - prev_equity) / prev_equity)
    return returns


def _periods_per_year(equity_curve: list[tuple[datetime, float]]) -> float:
    """Annualization factor derived from the equity curve's own average bar
    spacing — timeframe-independent, no separate TimeFrame input needed."""
    if len(equity_curve) < 2:
        return 0.0
    total_seconds = (equity_curve[-1][0] - equity_curve[0][0]).total_seconds()
    if total_seconds <= 0:
        return 0.0
    avg_seconds_per_bar = total_seconds / (len(equity_curve) - 1)
    return _SECONDS_PER_YEAR / avg_seconds_per_bar


def _sharpe_and_sortino(
    equity_curve: list[tuple[datetime, float]],
) -> tuple[float, float]:
    """@brief Risk-free rate assumed 0 (no risk-free-rate input anywhere in
    this codebase). Both 0.0 (never NaN/Inf) whenever the relevant
    volatility is 0 — fewer than 2 per-bar returns, every return identical
    (Sharpe), or no negative returns to measure (Sortino)."""
    returns = _bar_returns(equity_curve)
    if len(returns) < 2:
        return 0.0, 0.0

    periods_per_year = _periods_per_year(equity_curve)
    annualization = periods_per_year**0.5
    mean_return = statistics.fmean(returns)

    stdev = statistics.stdev(returns)
    sharpe = (
        0.0
        if math.isclose(stdev, 0.0, abs_tol=_ZERO_VOLATILITY_TOLERANCE)
        else mean_return / stdev * annualization
    )

    downside_deviation = statistics.fmean(min(r, 0.0) ** 2 for r in returns) ** 0.5
    sortino = (
        0.0
        if math.isclose(downside_deviation, 0.0, abs_tol=_ZERO_VOLATILITY_TOLERANCE)
        else mean_return / downside_deviation * annualization
    )
    return sharpe, sortino


def _calmar_ratio(
    equity_curve: list[tuple[datetime, float]], max_drawdown_percent: float
) -> float:
    """@brief CAGR ÷ |max drawdown %|. 0.0 whenever there's no real
    drawdown to divide by, starting equity was 0, or the run spans under a
    day (a CAGR extrapolated from a near-zero year-fraction is not a
    meaningful annual rate)."""
    if not max_drawdown_percent or len(equity_curve) < 2:
        return 0.0
    start_equity = equity_curve[0][1]
    end_equity = equity_curve[-1][1]
    if start_equity <= 0:
        return 0.0
    years = (
        equity_curve[-1][0] - equity_curve[0][0]
    ).total_seconds() / _SECONDS_PER_YEAR
    if years < (1 / 365.25):
        return 0.0
    cagr_percent = ((end_equity / start_equity) ** (1 / years) - 1) * 100
    return cagr_percent / max_drawdown_percent


def _max_drawdown_duration_bars(equity_curve: list[tuple[datetime, float]]) -> int:
    """@brief Longest run of consecutive bars strictly below the running
    peak (Peak-to-Recovery Duration) — a drawdown still open at the run's
    end counts through the last bar, never "recovered" for this run."""
    if not equity_curve:
        return 0
    peak = equity_curve[0][1]
    current_duration = 0
    max_duration = 0
    for _, equity in equity_curve:
        if equity >= peak:
            peak = equity
            current_duration = 0
        else:
            current_duration += 1
            max_duration = max(max_duration, current_duration)
    return max_duration


def _max_consecutive_streaks(trades: list[Trade]) -> tuple[int, int]:
    """@brief Longest consecutive-win and consecutive-loss streaks, walked
    in the trades' own chronological order. A breakeven trade (pnl == 0)
    ends both streaks without starting a new one — same treatment
    TradingView gives a scratch trade."""
    max_wins = current_wins = 0
    max_losses = current_losses = 0
    for trade in trades:
        if trade.pnl > 0:
            current_wins += 1
            current_losses = 0
        elif trade.pnl < 0:
            current_losses += 1
            current_wins = 0
        else:
            current_wins = 0
            current_losses = 0
        max_wins = max(max_wins, current_wins)
        max_losses = max(max_losses, current_losses)
    return max_wins, max_losses
