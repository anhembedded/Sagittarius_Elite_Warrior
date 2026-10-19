"""`EPIC-033U`: profit, loss and state are coloured from the meaning table, and the
cell's text is what it was, so a colour is never the only signal."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_table_models import (
    BotsTableModel,
    sign_tone,
    state_tone,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit import meaning_colours
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)

from .bots_screen_fixtures import stored

_FOREGROUND = Qt.ItemDataRole.ForegroundRole


def _snapshot(screen, state: S, profit: str):
    bot = screen.view.model.bots[0]
    progress = BotProgress(
        realised_profit=Decimal(profit),
        completed_cycles=2,
        open_orders=0,
        inventory=Decimal(0),
        average_cost=None,
        reason="",
        reason_detail="",
        orders=(),
    )
    return dataclasses.replace(bot, state=state, progress=progress)


def _foreground(model: BotsTableModel, key: str):
    return model.data(model.index(0, model.column(key)), _FOREGROUND)


def _bots_model(screen) -> BotsTableModel:
    models = [m for m in screen.view.findChildren(BotsTableModel)]
    assert models, "the Bots screen holds a BotsTableModel"
    return models[0]


def _show(screen, state: S, profit: str) -> BotsTableModel:
    bots_model = _bots_model(screen)
    bots_model.set_rows([_snapshot(screen, state, profit)])
    return bots_model


def _on(base: str, monkeypatch) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Base, QColor(base))
    monkeypatch.setattr(QGuiApplication, "palette", staticmethod(lambda: palette))
    return palette


@pytest.mark.parametrize("base", ["white", "black"])
def test_profit_loss_and_state_take_the_meaning_tables_colour(
    base, open_bots_screen, monkeypatch
):
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    screen.settle()
    palette = _on(base, monkeypatch)
    table = _show(screen, S.RUNNING, "12.5")
    assert _foreground(table, "grid_profit") == tone_colour(Tone.POSITIVE, palette)
    assert _foreground(table, "state") == tone_colour(Tone.POSITIVE, palette)
    table = _show(screen, S.HALTED, "-3.25")
    assert _foreground(table, "grid_profit") == tone_colour(Tone.NEGATIVE, palette)
    assert _foreground(table, "state") == tone_colour(Tone.NEGATIVE, palette)
    table = _show(screen, S.PAUSED, "0")
    assert _foreground(table, "grid_profit") is None
    assert _foreground(table, "state") == tone_colour(Tone.CAUTION, palette)


def test_in_high_contrast_the_platform_keeps_every_colour(
    open_bots_screen, monkeypatch
):
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    screen.settle()
    _on("white", monkeypatch)
    monkeypatch.setattr(meaning_colours, "is_high_contrast", lambda: True)
    table = _show(screen, S.HALTED, "-3.25")
    assert [_foreground(table, key) for key in ("grid_profit", "state")] == [None] * 2


def test_the_cells_text_is_the_word_and_the_signed_figure(open_bots_screen):
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    screen.settle()
    table = _show(screen, S.HALTED, "-3.25")
    display = Qt.ItemDataRole.DisplayRole
    assert table.data(table.index(0, table.column("state")), display) == "Halted"
    assert table.data(table.index(0, table.column("grid_profit")), display) == Decimal(
        "-3.25"
    )


def test_a_figure_not_known_or_zero_has_no_verdict():
    assert sign_tone(None) is Tone.NEUTRAL
    assert sign_tone(Decimal(0)) is Tone.NEUTRAL
    assert sign_tone(Decimal("0.01")) is Tone.POSITIVE
    assert sign_tone(Decimal("-0.01")) is Tone.NEGATIVE


def test_every_lifecycle_state_has_a_tone_and_only_the_quiet_ones_none():
    quiet = {S.DRAFT, S.STARTING, S.STOPPING, S.STOPPED}
    assert {s for s in S if state_tone(s) is Tone.NEUTRAL} == quiet


def test_a_ladder_cycle_that_loses_after_fees_is_coloured_as_a_loss(monkeypatch):
    from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_table_models import (
        BotLadderTableModel,
    )

    palette = _on("white", monkeypatch)
    ladder = BotLadderTableModel()
    key = ladder.column("net_quote")

    def row(net: Decimal | None):
        return type("Row", (), {"net_quote": net})()

    colours = [
        ladder._role_data(row(n), key, _FOREGROUND)
        for n in (Decimal(-1), Decimal(2), None)
    ]
    assert colours == [
        tone_colour(Tone.NEGATIVE, palette),
        tone_colour(Tone.POSITIVE, palette),
        None,
    ]
    assert ladder._role_data(row(Decimal(2)), ladder.column("net"), _FOREGROUND) is None
