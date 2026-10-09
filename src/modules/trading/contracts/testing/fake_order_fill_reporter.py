"""`BOT-173` — an `IOrderFillReporter` that keeps what it was told, for tests."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_fill_reporter import (
    IOrderFillReporter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order


@dataclass(frozen=True)
class ReportedFill:
    order: Order
    fill: tuple[Decimal, Decimal]
    fee: tuple[Decimal, str] | None
    trade_id: int | None


class FakeOrderFillReporter(IOrderFillReporter):
    """Every report, in order, with no de-duplication of its own."""

    def __init__(self) -> None:
        self.reported: list[ReportedFill] = []

    def order_filled(
        self,
        order: Order,
        fill: tuple[Decimal, Decimal],
        fee: tuple[Decimal, str] | None = None,
        trade_id: int | None = None,
    ) -> None:
        self.reported.append(ReportedFill(order, fill, fee, trade_id))
