"""`BOT-193` — a Grid bot's ladder as the JSON `bot show` and `bot list` carry under `ladder`.

Exact decimals as text (never a float), `null` where the record cannot give a figure, so a script
tells "unknown" from zero as a person does. Keys are added within a version, never renamed
(`test_the_bot_report_payload_keys_are_pinned`). A bot with no ladder says why under `reason`.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import (
    GridLadder,
    LadderRow,
    LadderUnavailable,
    PriceMark,
)


def ladder_payload(
    ladder: GridLadder | LadderUnavailable | None,
) -> dict[str, JsonValue] | None:
    """`None` for a bot that was not asked about its ladder."""
    if ladder is None:
        return None
    if isinstance(ladder, LadderUnavailable):
        return {"available": False, "reason": ladder.reason}
    summary = ladder.summary
    position = ladder.position
    return {
        "available": True,
        "reason": None,
        "spacing": summary.spacing.value,
        "smallest_step_fraction": str(summary.smallest_step_fraction),
        "largest_step_fraction": str(summary.largest_step_fraction),
        "maker_fee": _text(summary.maker_fee),
        "average_cycle_quote": _text(summary.average_cycle_quote),
        "recorded": {
            "completed_cycles": ladder.recorded.completed_cycles,
            "grid_profit": _text(ladder.recorded.grid_profit),
            "average_profit": _text(ladder.recorded.average_profit),
        },
        "position": {
            "last_price": _text(position.last_price),
            "age_seconds": position.age_seconds,
            "lower": _mark(position.lower),
            "upper": _mark(position.upper),
            "stop_loss": None
            if position.stop_loss is None
            else _mark(position.stop_loss),
            "take_profit": (
                None if position.take_profit is None else _mark(position.take_profit)
            ),
            "has_liquidation_price": position.has_liquidation_price,
        },
        "run_note": ladder.run_note,
        "rows": [_row(row) for row in ladder.rows],
    }


def _row(row: LadderRow) -> dict[str, JsonValue]:
    return {
        "buy": str(row.buy),
        "sell": str(row.sell),
        "step_fraction": str(row.step_fraction),
        "net_fraction": _text(row.net_fraction),
        "gross_quote": _text(row.gross_quote),
        "net_quote": _text(row.net_quote),
        "state": row.state.name,
    }


def _mark(mark: PriceMark) -> dict[str, JsonValue]:
    return {
        "price": str(mark.price),
        "distance_fraction": _text(mark.distance_fraction),
    }


def _text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)
