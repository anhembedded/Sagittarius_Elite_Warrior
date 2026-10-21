"""`BOT-225` — a page's scroll area never gets narrower than the content it holds.

@details A bare `QScrollArea` reports a tiny minimum size, so a splitter or a dialog could squeeze
it and cut the content's right edge (`BUG-246`, `BOT-225`). The area asks for the content's width
plus its frame and the vertical bar, and nothing for the height.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.content_width_scroll_area import (
    ContentWidthScrollArea,
)

_CONTENT_WIDTH = 480


def _content() -> QWidget:
    """A page whose layout reports a minimum width, as a real page does."""
    content = QWidget()
    inner = QWidget()
    inner.setMinimumSize(_CONTENT_WIDTH, 900)
    QVBoxLayout(content).addWidget(inner)
    return content


def _area_around_a_wide_content(qtbot) -> ContentWidthScrollArea:
    area = ContentWidthScrollArea()
    area.setWidget(_content())
    qtbot.addWidget(area)
    return area


def test_the_area_is_at_least_as_wide_as_its_content_and_its_chrome(qtbot) -> None:
    area = _area_around_a_wide_content(qtbot)

    chrome = area.frameWidth() * 2 + area.verticalScrollBar().sizeHint().width()

    assert area.minimumSizeHint().width() >= _CONTENT_WIDTH + chrome


def test_a_plain_scroll_area_does_not_ask_for_it_so_the_override_is_what_holds(
    qtbot,
) -> None:
    plain = QScrollArea()
    plain.setWidgetResizable(True)
    plain.setWidget(_content())
    qtbot.addWidget(plain)

    assert plain.minimumSizeHint().width() < _CONTENT_WIDTH


def test_the_height_is_left_free_for_the_page_to_scroll(qtbot) -> None:
    area = _area_around_a_wide_content(qtbot)

    assert area.minimumSizeHint().height() < 900


def test_an_area_with_no_content_yet_reports_the_base_size(qtbot) -> None:
    area = ContentWidthScrollArea()
    qtbot.addWidget(area)

    assert area.minimumSizeHint() == QScrollArea.minimumSizeHint(area)
