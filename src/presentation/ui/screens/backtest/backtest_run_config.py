from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.value_objects.currency import Currency
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


@dataclass(frozen=True)
class BacktestRunConfig:
    """
    @brief Everything read off the Backtest Screen toolbar for one run,
    already validated and typed — grouped so `BackTestPresenter` never
    threads five loose primitives through its dispatch/background methods.
    """

    strategy_key: str
    timeframe: TimeFrame
    initial_balance: float
    start_time: datetime | None
    end_time: datetime | None
    #: Values for the selected strategy's declared input_*() parameters
    #: (BOT-047) — None (the default) runs every declared default, same as
    #: never having opened the "Thông số Bot" modal at all.
    strategy_params: dict[str, Any] | None = field(default=None)
    currency: Currency = Currency.USD
