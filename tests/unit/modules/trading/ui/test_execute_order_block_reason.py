"""`EPIC-028O` — the manual order panels name a crossed stop in words."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderStopRejection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.execute_order_block_reason import (
    format_execute_order_block_reason,
)


def test_a_crossed_stop_is_explained_with_the_rule_it_broke() -> None:
    text = format_execute_order_block_reason(
        ExecuteOrderStopRejection.STOP_ON_WRONG_SIDE
    )

    assert "buy stop must be above" in text
    assert "sell stop below" in text
