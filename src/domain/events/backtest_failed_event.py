from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestFailedEvent:
    """Fired when a backtest run cannot complete (e.g. no historical data)."""

    reason: str
