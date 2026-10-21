"""`EPIC-044C` - the Bots screen with a Grid waiting for its range, pictured for the owner.

Two frames of the real screen (`plan_table_frames`): a Spot bot started below its range and a Short
Futures bot started above it, light and dark, at the window sizes of the conformance suite, saved
under `SEW_UI_SCREENSHOTS` as `bots~waiting_<frame>@<W>x<H>.png` (the CI artifact `ui-screenshots`).
The checks keep each picture worth opening: not blank, the Plan's banner says what the bot waits
for in the owner's words, the state is the word and not a warning, and nothing is shown as placed.

Retire when: a reviewer no longer judges the UI from pictures of it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_table_frames import (
    build_frame,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.notice_bar import NoticeKind
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_screenshots import (
    SCHEMES,
    SCREENSHOT_DIR_ENV,
    apply_scheme,
    is_blank,
    restore_scheme,
    screenshot_name,
)

_SIZES = [(1024, 700), (1366, 768), (1920, 1080)]
#: The frame, the sentence its banner says.
_FRAMES = {
    "spot_waiting": "Waiting for the price to enter 60,000.00–70,000.00 (last price 58,250.00, 12 s ago)",
    "futures_short_waiting": "Waiting for the price to enter 60,000.00–70,000.00 (last price 71,400.00, 12 s ago)",
}


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("frame", sorted(_FRAMES))
@pytest.mark.parametrize("width_height", _SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_a_waiting_bot_is_pictured_in_both_schemes(
    qtbot, tmp_path: Path, frame: str, scheme: str, width_height: tuple[int, int]
) -> None:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    apply_scheme(app, scheme)
    try:
        view = build_frame(frame)
        assert isinstance(view, BotsView)
        qtbot.addWidget(view)
        view.resize(*width_height)
        view.show()
        qtbot.waitExposed(view)
        for _ in range(3):
            app.processEvents()

        image = view.grab().toImage()
        out_dir = Path(os.environ.get(SCREENSHOT_DIR_ENV, tmp_path))
        out_dir.mkdir(parents=True, exist_ok=True)
        name = screenshot_name(f"bots~waiting_{frame}", QSize(*width_height), scheme)
        assert image.save(str(out_dir / name))

        assert not is_blank(image)
        banner = view.plan.banner
        assert banner.isVisible()
        assert banner.text.startswith(_FRAMES[frame])
        assert banner.text.endswith("nothing is placed until it does")
        assert banner.kind is NoticeKind.INFORMATION
        assert view.identity.who.text().endswith("Waiting for the range")
    finally:
        restore_scheme(app)
