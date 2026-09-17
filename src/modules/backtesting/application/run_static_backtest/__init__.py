"""The static runner: one fast pass over stored candles.

`BacktestCancelled` used to live in this package and is re-exported rather than
moved again: PR 3.1c put it in `contracts/`, because it is an *answer* — every
caller that handles a run's outcome has to be able to name it, and a consumer
importing it from `application/` would be reaching past this module's published
surface for a type the port hands back.
"""

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_cancelled import (
    BacktestCancelled,
)

from .command import RunStaticBacktestCommand
from .handler import RunStaticBacktestCommandHandler

__all__ = [
    "BacktestCancelled",
    "RunStaticBacktestCommand",
    "RunStaticBacktestCommandHandler",
]
