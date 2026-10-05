"""The window's status bar holds what a screen offers as `IStatusSource`
(`EPIC-033H`, HLD §11.2.2), in every mode, beside the venue."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QLabel, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import NavMetadata
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import (
    ScreenDescriptor,
    ScreenRegistry,
)
from Sagittarius_Elite_Warrior.tests.unit.presentation.ui.main_window_fakes import (
    DisposeLog,
    ShownPresenter,
    engine,
    screen,
)


class _ConnectionView(QLabel):
    """A screen that knows the connection state and offers its word."""

    def __init__(self) -> None:
        super().__init__("a page")
        self.word = QLabel("Exchange: not checked")
        self.word.setObjectName("lblConnection")

    def status_widgets(self) -> Sequence[QWidget]:
        return (self.word,)


def test_a_screens_status_word_is_in_the_windows_status_bar_in_every_mode(
    qtbot,
) -> None:
    log = DisposeLog()
    registry = ScreenRegistry()
    registry.register(
        ScreenDescriptor(
            route="market",
            presenter_class=lambda view, container: ShownPresenter("market", log),
            view_factory=_ConnectionView,
            nav=NavMetadata(title="Market", icon="circle", item_sequence=5),
        )
    )
    registry.register(
        screen("trading.spot", "Spot", log, item_sequence=17, is_default=True)
    )
    window = MainWindow(engine(), registry, venue_text="SPOT TESTNET")
    qtbot.addWidget(window)
    window.show()

    bar = window.statusBar()
    word = bar.findChild(QLabel, "lblConnection")
    venue = bar.findChild(QLabel, "workbench::venue")
    assert word is not None
    assert venue is not None

    for mode in ("trading.spot", "market"):
        window.switch_screen(mode)
        assert word.isVisible(), mode
    assert word.text() == "Exchange: not checked"
