"""Every mode of the booted workbench is pictured at each window size, so a
reviewer can judge its layout by eye (`pr-review` SKILL §5.1).

Runs on every gate: the pictures go to a temporary directory, or to the one
`SEW_UI_SCREENSHOTS` names, which CI keeps as the `ui-screenshots`
artifact. The assertions keep the pictures worth looking at: one per mode,
none whose centre is blank.

Retire when: a reviewer no longer judges the UI from pictures of it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.test_workbench_conformance import (
    WINDOW_SIZES,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_screenshots import (
    SCREENSHOT_DIR_ENV,
    capture_modes,
    is_blank,
    screenshot_name,
)


@pytest.mark.parametrize(
    "size", [QSize(*s) for s in WINDOW_SIZES], ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
@pytest.mark.parametrize("app_engine", [True], indirect=True)
def test_every_mode_is_pictured_at_each_size(
    main_window, navigate, size: QSize, tmp_path: Path
) -> None:
    out_dir = Path(os.environ.get(SCREENSHOT_DIR_ENV) or tmp_path)

    saved = capture_modes(main_window, navigate, size, out_dir)

    routes = main_window.navigation.modes()
    assert [shot.path.name for shot in saved] == [
        screenshot_name(r, size) for r in routes
    ]
    unreadable = [s.path.name for s in saved if QImage(str(s.path)).isNull()]
    blank = [shot.route for shot in saved if is_blank(shot.centre)]
    assert not unreadable, f"unreadable pictures: {unreadable}"
    assert not blank, f"modes whose centre is blank: {blank}"


def test_a_flat_picture_is_blank_and_a_drawn_one_is_not(qapp) -> None:
    flat = QImage(320, 200, QImage.Format.Format_RGB32)
    flat.fill(QColor("white"))
    drawn = flat.copy()
    for x in range(drawn.width()):
        for y in range(drawn.height()):
            drawn.setPixel(x, y, QColor.fromHsv((x * 7 + y * 3) % 360, 200, 200).rgb())

    assert is_blank(flat)
    assert is_blank(QImage())
    assert not is_blank(drawn)
