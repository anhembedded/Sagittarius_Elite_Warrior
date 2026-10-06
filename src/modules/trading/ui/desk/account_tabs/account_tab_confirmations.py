"""`EPIC-028J` — the questions a desk's account tabs ask before acting at
the exchange.

@details Cancelling every open order and closing a position at market are
both irreversible at the venue, so each asks first and names what it acts
on (`Docs/HLD/11_desktop_workbench.md` §11.5). Injectable, in the shape
`OpenOrdersPanel`'s `ConfirmCancel` established, so a test drives the tabs
without a modal dialog waiting for a click.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    OpenOrderRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    PositionRow,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    write_value,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.verb_confirmation import (
    VerbQuestion,
    ask_with_verbs,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

type ConfirmCancelAll = Callable[[Sequence[OpenOrderRow]], bool]
type ConfirmClosePosition = Callable[[PositionRow], bool]


@dataclass(frozen=True)
class AccountTabConfirmations:
    """What the tabs ask before acting. `None` asks with a message box."""

    cancel_one: Callable[[OpenOrderRow], bool] | None = None
    cancel_all: ConfirmCancelAll | None = None
    close_position: ConfirmClosePosition | None = None


def cancel_all_question(rows: Sequence[OpenOrderRow]) -> str:
    symbols = sorted({row.symbol for row in rows})
    return (
        f"Cancel all {len(rows)} open orders shown ({', '.join(symbols)})?\n\n"
        "They are cancelled at the exchange and cannot be restored."
    )


def close_position_question(row: PositionRow) -> str:
    return (
        f"Close the {row.side.value.upper()} {row.symbol} position "
        f"({write_value(ColumnKind.QUANTITY, row.quantity)}) "
        "at market?\n\n"
        "A reduce-only market order for the whole position is sent; the "
        "fill price is the market's, not the mark price shown."
    )


def ask_to_cancel_all(parent: QWidget, rows: Sequence[OpenOrderRow]) -> bool:
    """Cancel all orders, asked with its verbs, Keep orders the default."""
    return ask_with_verbs(
        parent,
        VerbQuestion(
            title="Cancel All Orders",
            question=cancel_all_question(rows),
            act="Cancel all orders",
            keep="Keep orders",
        ),
    )


def ask_to_close(parent: QWidget, row: PositionRow) -> bool:
    """Close position, asked with its verbs, Keep position the default."""
    return ask_with_verbs(
        parent,
        VerbQuestion(
            title="Close Position",
            question=close_position_question(row),
            act="Close position",
            keep="Keep position",
        ),
    )
