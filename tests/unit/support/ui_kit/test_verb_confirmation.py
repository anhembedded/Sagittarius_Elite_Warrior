"""`EPIC-033I` — a risky action asks with its own verbs, the safe one the
default, and Esc keeps (`ui-presentation-rule.md` §10, MS `mess-confirm`).

The real `QMessageBox`, answered from the event loop once it is modal.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
from Sagittarius_Elite_Warrior.src.support.ui_kit.minimum_hint_slot import (
    MinimumHintSlot,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.verb_confirmation import (
    VerbQuestion,
    ask_with_verbs,
)

_QUESTION = VerbQuestion(
    title="Cancel Order",
    question="Cancel the BUY LIMIT order on BTCUSDT?",
    act="Cancel order",
    keep="Keep order",
    details="It cannot be restored.",
)


def _answer_with(act: Callable[[QMessageBox], None], seen: list[QMessageBox]) -> None:
    """Acts on the dialog once it is the modal one."""

    def answer() -> None:
        box = QApplication.activeModalWidget()
        assert isinstance(box, QMessageBox)
        seen.append(box)
        act(box)

    QTimer.singleShot(0, answer)


def _button(box: QMessageBox, text: str) -> QPushButton:
    return next(b for b in box.findChildren(QPushButton) if b.text() == text)


def test_the_acting_verb_acts(qapp) -> None:
    seen: list[QMessageBox] = []
    _answer_with(lambda box: _button(box, "Cancel order").click(), seen)

    assert ask_with_verbs(None, _QUESTION) is True
    (box,) = seen
    texts = sorted(b.text() for b in box.findChildren(QPushButton))
    assert texts == ["Cancel order", "Keep order"]
    assert box.windowTitle() == "Cancel Order"
    assert box.informativeText() == "It cannot be restored."


def test_the_keeping_verb_is_the_default_and_keeps(qapp) -> None:
    seen: list[QMessageBox] = []
    _answer_with(lambda box: _button(box, "Keep order").click(), seen)

    assert ask_with_verbs(None, _QUESTION) is False
    assert seen[0].defaultButton() is _button(seen[0], "Keep order")


def test_esc_keeps(qapp) -> None:
    seen: list[QMessageBox] = []
    _answer_with(lambda box: QTest.keyClick(box, Qt.Key.Key_Escape), seen)

    assert ask_with_verbs(None, _QUESTION) is False


def test_a_slot_asks_for_its_minimum(qtbot) -> None:
    content = QPushButton("a panel's table")
    content.setMinimumSize(40, 30)
    slot = MinimumHintSlot(content)
    qtbot.addWidget(slot)

    assert slot.sizeHint() == slot.minimumSizeHint()
    assert content.parentWidget() is slot
