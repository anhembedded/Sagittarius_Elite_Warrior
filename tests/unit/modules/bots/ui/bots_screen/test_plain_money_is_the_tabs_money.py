"""`BOT-192` - the commands write money without Qt, and write it as the Bots tab does."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    plain_money,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import write_value
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-0.001",
        "0.004",
        "0.005",
        "5.74",
        "-9",
        "1234.5",
        "-1234.567",
        "1000000.999",
    ],
)
def test_plain_money_writes_what_the_tabs_formatter_writes(value: str) -> None:
    assert plain_money(Decimal(value)) == write_value(ColumnKind.MONEY, float(value))
