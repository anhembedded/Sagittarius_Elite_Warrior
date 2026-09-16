"""`BOT-129` — content must scroll when it overflows, not be squashed into the
viewport.

The bug these lock: a plain `QScrollArea` with `setWidgetResizable(True)` only
scrolls once the content's **minimum** height stops fitting. A column of cards
can shrink far below the height it asks for, so Qt compressed it instead and no
scroll bar ever appeared — measured on the real Trading screen at 1920x1080 as
1178px of wanted height crammed into 647px.

Each test below is written against a content widget that *can* shrink, because
that is the only shape where the two behaviours differ: content with a large
minimum (Backtest's) scrolls either way, which is exactly why the defect looked
like "only Backtest has scrolling".
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit.preferred_height_scroll_area import (
    PreferredHeightScrollArea,
)

#: Tall enough that the content cannot fit the viewport below, short enough to
#: stay a unit test. The exact values do not matter, only that content wants
#: more than it is given.
_ROW_COUNT = 12
_ROW_HEIGHT = 40
_ROW_MINIMUM_HEIGHT = 5
_VIEWPORT_HEIGHT = 150


class _CompressibleRow(QWidget):
    """Asks for `_ROW_HEIGHT` but will shrink to `_ROW_MINIMUM_HEIGHT`.

    The distinction is the whole bug. A row built with `setFixedHeight()`
    scrolls under a plain `QScrollArea` too, because its minimum *is* its
    preferred — which is why an earlier draft of these tests proved nothing
    and the baseline test below caught that.
    """

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return QSize(100, _ROW_HEIGHT)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return QSize(100, _ROW_MINIMUM_HEIGHT)


def _compressible_content() -> QWidget:
    """A column that asks for `_ROW_COUNT * _ROW_HEIGHT` but whose minimum is a
    twelfth of that — the shape that made the real screens squash rather than
    scroll."""
    content = QWidget()
    layout = QVBoxLayout(content)
    for _ in range(_ROW_COUNT):
        layout.addWidget(_CompressibleRow())
    return content


def _laid_out(area: QScrollArea, content: QWidget) -> QScrollArea:
    area.setWidget(content)
    area.resize(400, _VIEWPORT_HEIGHT)
    area.show()
    return area


def test_a_plain_scroll_area_squashes_this_content(qtbot) -> None:
    """The defect itself, pinned as the baseline the class has to beat.

    Not a test of Qt: it is the proof that the two behaviours actually differ
    for this content shape. If Qt ever changed and this started scrolling, the
    class below would be solving a problem that no longer exists — and this
    test failing is how anyone would find out.
    """
    plain = QScrollArea()
    plain.setWidgetResizable(True)
    qtbot.addWidget(plain)

    _laid_out(plain, _compressible_content())

    assert plain.verticalScrollBar().maximum() == 0


def test_content_taller_than_the_viewport_scrolls(qtbot) -> None:
    area = PreferredHeightScrollArea()
    qtbot.addWidget(area)

    _laid_out(area, _compressible_content())

    assert area.verticalScrollBar().maximum() > 0


def test_the_content_keeps_the_height_it_asked_for(qtbot) -> None:
    """The mechanism, stated directly: the scrollable range exists because the
    content was not compressed, not because a fixed height was imposed."""
    area = PreferredHeightScrollArea()
    qtbot.addWidget(area)
    content = _compressible_content()

    _laid_out(area, content)

    assert content.height() >= content.sizeHint().height()


def test_content_that_fits_is_not_given_a_scroll_bar(qtbot) -> None:
    """The other half of the contract — a short panel must not grow a scroll
    bar just because it is wrapped in one of these."""
    area = PreferredHeightScrollArea()
    qtbot.addWidget(area)
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.addWidget(QLabel("one short row"))

    area.setWidget(content)
    area.resize(400, 600)
    area.show()

    assert area.verticalScrollBar().maximum() == 0


def test_content_that_grows_later_becomes_scrollable(qtbot) -> None:
    """Screens add rows after construction (a filled trade table, a card shown
    on a state change). A one-shot measurement at `setWidget()` time would miss
    every one of those."""
    area = PreferredHeightScrollArea()
    qtbot.addWidget(area)
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.addWidget(QLabel("only row"))
    area.setWidget(content)
    area.resize(400, _VIEWPORT_HEIGHT)
    area.show()
    assert area.verticalScrollBar().maximum() == 0

    for _ in range(_ROW_COUNT):
        layout.addWidget(_CompressibleRow())
    content.adjustSize()
    qtbot.waitUntil(lambda: area.verticalScrollBar().maximum() > 0, timeout=2000)

    assert area.verticalScrollBar().maximum() > 0
