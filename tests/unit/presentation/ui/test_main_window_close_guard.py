"""`EPIC-029F` (ADR O4) — closing the window while a context objects asks
first, and Cancel keeps everything running."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from unittest.mock import Mock, patch

import pytest
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.i_close_objections import (
    ICloseObjection,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.close_confirmation import (
    close_question,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.shell.close_objections import CloseObjections
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import IScreenRegistry


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
def open_window(qtbot) -> Iterator:
    def build(objection: _Says, answers: _Answers) -> tuple[MainWindow, Mock]:
        app_engine = Mock()
        registry = Mock(spec=IScreenRegistry)
        registry.get_default_route.return_value = "welcome"
        registry.build_sidebar_navigation.return_value = ((), ())
        sidebar = QWidget()
        sidebar.sig_navigate = Mock()  # type: ignore[attr-defined]
        sidebar.collapsed_changed = Mock()  # type: ignore[attr-defined]
        sidebar.set_active = Mock()  # type: ignore[attr-defined]
        objections = CloseObjections()
        objections.register(objection)
        window = MainWindow(
            app_engine,
            registry,
            Mock(return_value=sidebar),
            close_objections=objections,
            confirm_close=answers,
        )
        qtbot.addWidget(window)
        window.show()
        return window, window._router

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.ui.main_window.PresenterManager"
    ):
        yield build


def test_cancel_keeps_the_window_and_shuts_nothing_down(open_window) -> None:
    answers = _Answers(False)
    window, router = open_window(_Says("Bots still active: grid one"), answers)

    assert window.close() is False

    assert window.isVisible()
    assert answers.asked == [("Bots still active: grid one",)]
    router.shutdown.assert_not_called()


def test_close_anyway_shuts_down_and_closes(open_window) -> None:
    answers = _Answers(True)
    window, router = open_window(_Says("Bots still active: grid one"), answers)

    assert window.close() is True

    assert not window.isVisible()
    router.shutdown.assert_called_once()


def test_nothing_to_object_closes_without_asking(open_window) -> None:
    answers = _Answers(False)
    window, router = open_window(_Says(None), answers)

    assert window.close() is True

    assert answers.asked == []
    router.shutdown.assert_called_once()


def test_the_question_lists_every_reason_then_asks() -> None:
    question = close_question(["bots running", "export unsaved"])

    assert question.index("bots running") < question.index("export unsaved")
    assert question.endswith("Close the app anyway?")
