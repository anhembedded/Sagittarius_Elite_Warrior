"""`BOT-225` - the State of a refused key is readable whole in the Options dialog at any size.

@details The `-2015` sentence is two hundred characters. In a State column of the dialog's minimum
width it got 75 px and 12 px of height where its text needs 375: the grid does not carry
height-for-width into a dialog's minimum size. The sentence is now a line of its own under its
venue, in a page that scrolls once at itself, so its label always holds its wrapped text.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.ui.settings.key_page_world import (
    KEY,
    build_page,
    mainnet_accepts,
    status_of,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.options_dialog import (
    OptionsDialog,
)

_VENUE = TradingVenue.FUTURES_MAINNET


def _refused_key_label(qapp, tmp_path, request, size: QSize | None) -> QLabel:
    page = build_page(tmp_path, request)
    page.probe.verdicts = mainnet_accepts(futures=True)
    page.type_in_dialog(KEY)
    page.click_add()
    page.statuses.by_venue[_VENUE] = status_of(
        _VENUE, ConnectionFailureKind.KEY_REJECTED
    )
    page.click_check()
    dialog = OptionsDialog([page.presenter])
    dialog.show()
    # A person drags the dialog down to its minimum; the label's hint follows its width, so the
    # minimum is read again after each settle until it stops moving.
    for _ in range(5):
        dialog.resize(size or dialog.minimumSizeHint())
        qapp.processEvents()
    label = dialog.findChild(QLabel, f"lblKeyState_{_VENUE.name}::text")
    assert label is not None
    # The dialog is closed by the test's teardown; keep it alive until the label was read.
    label.setProperty("dialog", dialog)
    return label


@pytest.mark.parametrize(
    "size",
    [None, QSize(520, 400), QSize(900, 700)],
    ids=["minimum", "narrow", "wide"],
)
def test_the_sentence_has_the_height_its_wrapped_text_needs(
    qapp, tmp_path, request, size: QSize | None
) -> None:
    label = _refused_key_label(qapp, tmp_path, request, size)

    assert label.text().startswith("Error:")
    assert len(label.text()) > 100
    assert label.height() >= label.heightForWidth(label.width())
