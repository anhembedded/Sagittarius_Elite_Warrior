"""`EPIC-029F` (ADR O4) — closing the window while a context objects asks
first, and Cancel keeps everything running."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_close_objections import (
    ICloseObjection,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.close_confirmation import (
    close_question,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.shell.close_objections import CloseObjections
from Sagittarius_Elite_Warrior.tests.unit.presentation.ui.main_window_fakes import (
    DisposeLog,
    engine,
    three_screens,
)


class _Says(ICloseObjection):
    def __init__(self, reason: str | None) -> None:
        self.reason = reason

    def objection(self) -> str | None:
        return self.reason


class _Answers:
    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.asked: list[tuple[str, ...]] = []

    def __call__(self, reasons: Sequence[str]) -> bool:
        self.asked.append(tuple(reasons))
        return self.answer


@pytest.fixture
def open_window(qtbot):
    def build(objection: _Says, answers: _Answers) -> tuple[MainWindow, DisposeLog]:
        log = DisposeLog()
        objections = CloseObjections()
        objections.register(objection)
        window = MainWindow(
            engine(),
            three_screens(log),
            close_objections=objections,
            confirm_close=answers,
        )
        qtbot.addWidget(window)
        window.show()
        return window, log

    return build


def test_cancel_keeps_the_window_and_shuts_nothing_down(open_window) -> None:
    answers = _Answers(False)
    window, log = open_window(_Says("Bots still active: grid one"), answers)

    assert window.close() is False

    assert window.isVisible()
    assert answers.asked == [("Bots still active: grid one",)]
    assert log.routes == []


def test_close_anyway_shuts_down_and_closes(open_window) -> None:
    answers = _Answers(True)
    window, log = open_window(_Says("Bots still active: grid one"), answers)

    assert window.close() is True

    assert not window.isVisible()
    assert log.routes == ["settings", "trading.spot", "trading.futures"]


def test_nothing_to_object_closes_without_asking(open_window) -> None:
    answers = _Answers(False)
    window, log = open_window(_Says(None), answers)

    assert window.close() is True

    assert answers.asked == []
    assert log.routes == ["settings", "trading.spot", "trading.futures"]


def test_the_question_lists_every_reason_then_asks() -> None:
    question = close_question(["bots running", "export unsaved"])

    assert question.index("bots running") < question.index("export unsaved")
    assert question.endswith("Close the app anyway?")
