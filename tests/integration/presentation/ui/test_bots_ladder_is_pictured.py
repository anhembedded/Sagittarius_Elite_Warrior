"""The Bots mode of the booted workbench with a seeded running Grid bot and its Ladder panel in
front, pictured for a reviewer (`pr-review` SKILL §5.1; `BOT-193`).

The booted window in `test_workbench_screenshots.py` has no bot in its Bots mode, so the new Ladder
table and the Plan's grid step, profit per cycle and price position were in no picture. Here the
same real window is given the bot the preview fixture seeds (`bots_screen/preview.py` →
`seed_ladder_preview`), shown at each window size of the conformance suite and saved under
`SEW_UI_SCREENSHOTS` as `bots~ladder@<W>x<H>.png`. The assertions keep each picture worth opening:
the Ladder table is visible and shows its grids, and the picture is not blank.

Retire when: a reviewer no longer judges the UI from pictures of it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QTableView
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.preview import (
    seed_ladder_preview,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.test_workbench_conformance import (
    WINDOW_SIZES,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_screenshots import (
    SCREENSHOT_DIR_ENV,
    is_blank,
)


@pytest.mark.parametrize(
    "size", [QSize(*s) for s in WINDOW_SIZES], ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
@pytest.mark.parametrize("app_engine", [True], indirect=True)
def test_the_seeded_ladder_is_pictured_at_each_size(
    main_window, navigate, size: QSize, tmp_path: Path
) -> None:
    out_dir = Path(os.environ.get(SCREENSHOT_DIR_ENV) or tmp_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    main_window.resize(size)
    main_window.show()
    navigate(BOTS_ROUTE)
    view = main_window.hosts[BOTS_ROUTE].findChild(BotsView)
    assert view is not None
    seed_ladder_preview(view)
    for _ in range(3):
        QApplication.processEvents()

    picture = main_window.grab()
    path = out_dir / f"bots~ladder@{size.width()}x{size.height()}.png"

    assert picture.save(str(path)), f"could not write {path}"
    assert not is_blank(picture.toImage())
    table = view.findChild(QTableView, "tblBotLadder")
    assert table is not None and table.isVisible()
    assert table.model().rowCount() > 0
