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

from PySide6.QtWidgets import QMessageBox, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    OpenOrderRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    PositionRow,
)

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
        f"({row.quantity_text}) at market?\n\n"
        "A reduce-only market order for the whole position is sent; the "
        "fill price is the market's, not the mark price shown."
    )


def ask_with_message_box(parent: QWidget, title: str, question: str) -> bool:
    answer = QMessageBox.question(
        parent,
        title,
        question,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes
