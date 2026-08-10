from dataclasses import dataclass


@dataclass(frozen=True)
class StopBacktestCommand:
    """
    @brief Command to stop the globally running backtest simulation.
    """
