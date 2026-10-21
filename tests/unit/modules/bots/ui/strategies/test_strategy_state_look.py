"""`EPIC-043E` — an armed venue's state is a word with an icon and a tone beside it; a venue that is
not armed is the word alone."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.strategy_rows import (
    ARMED_LOOK,
    ARMED_TEXT,
    NOT_ARMED_TEXT,
    StrategyRow,
    StrategyRowsModel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)

_STATE = StrategyRowsModel.column("state")
_VENUE_COLUMN = StrategyRowsModel.column("venue")


def _model(*rows: StrategyRow) -> StrategyRowsModel:
    model = StrategyRowsModel()
    model.set_rows(list(rows))
    return model


def _armed() -> StrategyRow:
    return StrategyRow(TradingVenue.FUTURES_TESTNET, "EMA cross on BTCUSDT 1m")


def _idle() -> StrategyRow:
    return StrategyRow(TradingVenue.SPOT_TESTNET, "")


def _role(model: StrategyRowsModel, row: int, column: int, role: Qt.ItemDataRole):
    return model.data(model.index(row, column), role)


def test_an_armed_state_has_its_icon_and_the_profit_tone_beside_the_word(qapp) -> None:
    model = _model(_armed())

    icon = _role(model, 0, _STATE, Qt.ItemDataRole.DecorationRole)
    colour = _role(model, 0, _STATE, Qt.ItemDataRole.ForegroundRole)

    assert icon is not None and not icon.isNull()
    assert colour == tone_colour(Tone.POSITIVE, QGuiApplication.palette())
    assert _role(model, 0, _STATE, Qt.ItemDataRole.DisplayRole) == ARMED_TEXT


def test_a_venue_that_is_not_armed_is_the_word_alone(qapp) -> None:
    model = _model(_idle())

    assert _role(model, 0, _STATE, Qt.ItemDataRole.DecorationRole) is None
    assert _role(model, 0, _STATE, Qt.ItemDataRole.ForegroundRole) is None
    assert _role(model, 0, _STATE, Qt.ItemDataRole.DisplayRole) == NOT_ARMED_TEXT


def test_no_other_column_has_an_icon_or_a_tone(qapp) -> None:
    model = _model(_armed())
    others = [c for c in range(model.columnCount()) if c != _STATE]

    for column in others:
        assert _role(model, 0, column, Qt.ItemDataRole.DecorationRole) is None
        assert _role(model, 0, column, Qt.ItemDataRole.ForegroundRole) is None


def test_the_armed_look_is_a_lucide_icon_in_the_profit_tone() -> None:
    assert (ARMED_LOOK.icon, ARMED_LOOK.tone) == ("zap", Tone.POSITIVE)
