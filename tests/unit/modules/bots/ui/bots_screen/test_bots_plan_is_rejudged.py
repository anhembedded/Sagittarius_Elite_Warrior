"""`BUG-193` — the Plan, the chart's ladder and Save follow what is on screen.

The owner's real app: Grids changed from 10 to 5 and Save pressed; the log said
"done" but the stored bot kept 10 grids, the chart kept the old ladder and the
verdict kept "3.33 after the fee, below the exchange minimum of 5". Every test
drives the real Grid panel with real key events over the screen's real
composition (`open_screen`); the only fakes are the venue's ports.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import (
    BotOverlay,
    OverlayRole,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_panel import (
    GridPanel,
)

from .bots_market_fixtures import SYMBOL, terms
from .bots_screen_fixtures import GOOD_CONFIG, BotsScreen, stored
from .connect_screen_helpers import fresh_snapshot, select

#: Ten levels of 3.5 USDT, 3.49 after the fee: under the 5 USDT minimum. Five
#: levels of 7 pass.
TEN_GRIDS = {**GOOD_CONFIG, "capital_quote": "35", "grid_count": "10"}
_REFUSED = "below the exchange minimum"


def _panel(screen: BotsScreen) -> GridPanel:
    panel = screen.view._kind_panel
    assert isinstance(panel, GridPanel)
    return panel


def _selected_ten_grid_draft(open_bots_screen: Any) -> BotsScreen:
    screen = open_bots_screen([stored("a00001", S.DRAFT, TEN_GRIDS)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    return screen


def _step_grids_down_to(panel: GridPanel, count: int) -> None:
    """The user's gesture: the spin box's down arrow, one press per step."""
    panel.grid_count.setFocus()
    while panel.grid_count.value() > count:
        QTest.keyClick(panel.grid_count, Qt.Key.Key_Down)


def _drawn(screen: BotsScreen, monkeypatch: Any) -> list[BotOverlay | None]:
    """Every overlay the chart host is asked to draw (the real method still runs)."""
    host, drawn = screen.presenter._charts, []
    real = host.draw

    def record(overlay: BotOverlay | None) -> None:
        drawn.append(overlay)
        real(overlay)

    monkeypatch.setattr(host, "draw", record)
    return drawn


def _readiness(screen: BotsScreen) -> str:
    readiness = screen.view.model.readiness
    return readiness.message() if readiness is not None else ""


def _levels(overlay: BotOverlay) -> int:
    """The grid's own levels on the chart (not the range edges or the price)."""
    ladder = {OverlayRole.BUY_LEVEL, OverlayRole.SELL_LEVEL}
    return sum(1 for line in overlay.lines if line.role in ladder)


def _verdict_text(screen: BotsScreen) -> str:
    return " ".join(screen.view.model.verdict_lines)


def test_grids_stepped_with_the_arrows_are_judged_and_drawn_at_once(
    open_bots_screen: Any, monkeypatch: Any
) -> None:
    screen = _selected_ten_grid_draft(open_bots_screen)
    assert _REFUSED in _verdict_text(screen)
    drawn = _drawn(screen, monkeypatch)

    _step_grids_down_to(_panel(screen), 5)
    screen.presenter._rejudge.timeout.emit()

    assert _REFUSED not in _verdict_text(screen)
    assert drawn and drawn[-1] is not None
    assert _levels(drawn[-1]) == 5


def test_save_stores_the_grids_on_screen_and_judges_what_it_stored(
    open_bots_screen: Any, monkeypatch: Any
) -> None:
    screen = _selected_ten_grid_draft(open_bots_screen)
    _step_grids_down_to(_panel(screen), 5)
    drawn = _drawn(screen, monkeypatch)

    screen.view.model.action_requested.emit(BotAction.SAVE.value)
    screen.settle()

    saved = screen.store.load(BotId("a00001"))
    assert saved.bot.definition.config["grid_count"] == "5"
    assert _REFUSED not in _verdict_text(screen)
    assert "blocked" not in screen.view.status.text()
    assert drawn and drawn[-1] is not None
    assert _levels(drawn[-1]) == 5


def test_save_stores_what_the_editor_shows_even_when_a_widget_said_nothing(
    open_bots_screen: Any,
) -> None:
    """The mechanism under the arrows: Save reads the editor at the click, so a
    widget that missed a signal (now or in a later kind) cannot save old values."""
    screen = _selected_ten_grid_draft(open_bots_screen)
    spin = _panel(screen).grid_count
    spin.blockSignals(True)
    spin.setValue(5)
    spin.blockSignals(False)

    screen.view.model.action_requested.emit(BotAction.SAVE.value)
    screen.settle()

    saved = screen.store.load(BotId("a00001"))
    assert saved.bot.definition.config["grid_count"] == "5"


def test_a_recovered_connection_judges_the_plan_again_without_a_user_action(
    open_bots_screen: Any, caplog: Any
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    entry = terms().terms_for(SYMBOL)
    screen.venue_terms.unlist(SYMBOL)
    screen.account.answer_with(fresh_snapshot())
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    assert "cannot be judged" in _readiness(screen)

    screen.venue_terms.answer_with(entry)
    with caplog.at_level("INFO", logger="App.Bots.Screen"):
        screen.view.model.retry_connect_requested.emit()
        screen.settle()

    assert "cannot be judged" not in _readiness(screen)
    assert screen.view.model.availability[BotAction.START].enabled
    told = [r for r in caplog.records if "[plan-rejudge]" in r.getMessage()]
    assert len(told) == 1 and told[0].levelname == "INFO"
    assert "no terms seeded" in told[0].getMessage()
