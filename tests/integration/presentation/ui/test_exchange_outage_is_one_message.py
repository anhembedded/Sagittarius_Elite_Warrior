"""`BOT-169` — a booted app whose exchange answers an HTML `502` tells the user once.

On 2026-10-07 the Spot Testnet answered a gateway's `502` page and one screen
read failed four times within 50 ms. The Trade mode is booted over the fake
server with an outage switched on, and every read its desk starts fails: the
user must see one message bar in the Trade mode, no message box, and no page
in any label; the bar goes when the exchange answers again.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.trade_mode_boot import (
    TRADE_ROUTE,
    Boot,
    TradeDesk,
    trade_mode_running,
)

_WAIT_MS = 10_000


@pytest.fixture
def trade_boot(request: pytest.FixtureRequest) -> Boot:
    return Boot.from_request(request)


@pytest.fixture
def spot_desk(trade_boot: Boot) -> Iterator[TradeDesk]:
    with trade_mode_running(trade_boot) as desk:
        yield desk


def _bars(desk: TradeDesk):
    return desk.window.hosts[TRADE_ROUTE].message_bars


def _open_boxes() -> list[QMessageBox]:
    return [
        w
        for w in QApplication.topLevelWidgets()
        if isinstance(w, QMessageBox) and w.isVisible()
    ]


def test_one_outage_is_one_bar_and_no_dialog_and_no_page(spot_desk, qtbot) -> None:
    desk = spot_desk
    desk.urls.outage.set()

    # Every read the desk makes: the account tabs, the summary, the histories.
    desk.presenter.tabs.refresh()
    desk.presenter.summary.refresh()
    desk.presenter.order_entry.refresh()

    qtbot.waitUntil(lambda: _bars(desk).bar_count() > 0, timeout=_WAIT_MS)
    qtbot.wait(300)  # let the rest of the burst land
    assert _bars(desk).bar_count() == 1
    assert _open_boxes() == []
    page_words = ("<html", "<title>", "nginx")
    for label in desk.window.findChildren(QLabel):
        assert not any(word in label.text() for word in page_words), label.objectName()


def test_the_bar_goes_when_the_exchange_answers_again(spot_desk, qtbot) -> None:
    desk = spot_desk
    desk.urls.outage.set()
    desk.presenter.tabs.refresh()
    qtbot.waitUntil(lambda: _bars(desk).bar_count() > 0, timeout=_WAIT_MS)

    desk.urls.outage.clear()
    desk.presenter.tabs.refresh()

    qtbot.waitUntil(lambda: _bars(desk).bar_count() == 0, timeout=_WAIT_MS)
