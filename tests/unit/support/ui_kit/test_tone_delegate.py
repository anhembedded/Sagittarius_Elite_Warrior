"""`EPIC-043C`: a cell of a tree or list names its tone in `TONE_ROLE` and is painted in it."""

from __future__ import annotations

import pytest
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QPalette,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import QStyleOptionViewItem, QTreeView
from Sagittarius_Elite_Warrior.src.support.ui_kit import meaning_colours
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.tone_delegate import (
    TONE_ROLE,
    ToneKindDelegate,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    APP_VALUE_FORMATTER,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind, ColumnSpec

_TEXT = QPalette.ColorRole.Text
_COLUMNS = (ColumnSpec("finding", "Finding", ColumnKind.TEXT),)


def _text_colour(tone: Tone | None, qtbot) -> QColor:
    model = QStandardItemModel(0, 1)
    item = QStandardItem("a sentence")
    if tone is not None:
        item.setData(tone, TONE_ROLE)
    model.appendRow([item])
    view = QTreeView()
    qtbot.addWidget(view)
    delegate = ToneKindDelegate(_COLUMNS, APP_VALUE_FORMATTER, view)
    option = QStyleOptionViewItem()
    delegate.initStyleOption(option, model.index(0, 0))
    return option.palette.color(_TEXT)


def test_a_cell_is_painted_in_the_colour_of_its_tone(qtbot) -> None:
    palette = QGuiApplication.palette()

    assert _text_colour(Tone.NEGATIVE, qtbot) == tone_colour(Tone.NEGATIVE, palette)
    assert _text_colour(Tone.CAUTION, qtbot) == tone_colour(Tone.CAUTION, palette)
    assert _text_colour(Tone.NEGATIVE, qtbot) != _text_colour(Tone.POSITIVE, qtbot)


@pytest.mark.parametrize("tone", [None, Tone.NEUTRAL])
def test_a_cell_with_no_verdict_keeps_the_platforms_colour(
    tone: Tone | None, qtbot
) -> None:
    assert _text_colour(tone, qtbot) == QStyleOptionViewItem().palette.color(_TEXT)


def test_in_high_contrast_the_platform_keeps_the_colour(
    qtbot, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(meaning_colours, "is_high_contrast", lambda: True)

    assert _text_colour(Tone.NEGATIVE, qtbot) == QStyleOptionViewItem().palette.color(
        _TEXT
    )
