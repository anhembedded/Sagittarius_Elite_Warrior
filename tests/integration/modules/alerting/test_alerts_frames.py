"""`EPIC-036D2` — the Alerts screen as the owner meets it: light and dark at the three window
sizes the workbench suite uses, drawn by `QWidget.grab()` (no display needed); an integration test so the `Rest` part of the gate keeps them. With
`SEW_UI_SCREENSHOTS` set the pictures are kept for the owner to look at (the CI artifact
`ui-screenshots`); the checks are the measurable half: not blank, the table fits its width
(no horizontal scroll bar), and the failing-channel notice is shown, whole."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QStatusBar
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history.alerts_view import (
    AlertsView,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history.preview import (
    build_preview,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_screenshots import (
    SCHEMES,
    SCREENSHOT_DIR_ENV,
    apply_scheme,
    is_blank,
    restore_scheme,
    screenshot_name,
)

_SIZES = [(1024, 700), (1366, 768), (1920, 1080)]


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("width_height", _SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_the_alerts_screen_fits_and_reads_in_both_schemes(
    qtbot, tmp_path: Path, scheme: str, width_height: tuple[int, int]
) -> None:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    apply_scheme(app, scheme)
    try:
        view = build_preview()
        assert isinstance(view, AlertsView)
        qtbot.addWidget(view)
        view.resize(*width_height)
        view.show()
        qtbot.waitExposed(view)

        image = view.grab().toImage()
        out_dir = Path(os.environ.get(SCREENSHOT_DIR_ENV, tmp_path))
        out_dir.mkdir(parents=True, exist_ok=True)
        size = QSize(*width_height)
        assert image.save(
            str(out_dir / screenshot_name("alerts_preview", size, scheme))
        )

        assert not is_blank(image)
        table = view.history_table.view
        assert not table.horizontalScrollBar().isVisible()
        notice = view.findChild(type(view._notice), "noticeChannelFailing")
        assert notice is not None and notice.isVisible()
        assert view.notice_text.startswith("Telegram is not getting your alerts")
        assert view.notice_text.endswith("Tools → Options → Alerts.")
        _severity_tone_and_retry(view)
        _status_bar_frame(qtbot, view, out_dir, size, scheme)
    finally:
        restore_scheme(app)


def _severity_tone_and_retry(view: AlertsView) -> None:
    """`EPIC-036D5`: a critical alert's severity word is drawn in the meaning table's colour
    (its word is there too), and Retry failed is offered, whole."""
    model = view.history_table.view.model()
    severity = model.sourceModel().column("severity")
    tones = {
        model.index(row, severity).data(Qt.ItemDataRole.DisplayRole): model.index(
            row, severity
        ).data(Qt.ItemDataRole.ForegroundRole)
        for row in range(model.rowCount())
    }
    assert tones["Critical"] is not None
    assert tones["Info"] is None
    assert view.retry_button.isVisible()
    assert view.retry_button.text() == "Retry failed"


def _status_bar_frame(
    qtbot, view: AlertsView, out_dir: Path, size: QSize, scheme: str
) -> None:
    """The indicator where the window puts it (`EPIC-036D3`): a status bar holding the widget the
    view offers, with a channel failing, so its words and icon are in the picture."""
    bar = QStatusBar()
    qtbot.addWidget(bar)
    (indicator,) = view.status_widgets()
    bar.addPermanentWidget(indicator)
    bar.resize(size.width() // 2, 32)
    bar.show()
    qtbot.waitExposed(bar)

    image = bar.grab().toImage()

    assert image.save(str(out_dir / screenshot_name("alerts_indicator", size, scheme)))
    assert indicator.text() == "Alerts: Telegram failing"
    assert indicator.isVisible()
    assert not indicator.icon().isNull()
    assert not is_blank(image)
