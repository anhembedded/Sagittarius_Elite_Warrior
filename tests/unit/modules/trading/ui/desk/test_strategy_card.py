"""`EPIC-033P` stage 1 — the strategy card belongs to the desks and is built
from stock controls.

It moved out of the Dev Board's package, which the Developer mode deletes,
and names no screen's view model: it reads only its `StrategyCardBinding`.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QLabel,
    QPushButton,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.strategy_card.strategy_card import (
    StrategyCard,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.strategy_card.strategy_card_binding import (
    StrategyCardBinding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.strategy_card_view_model import (
    StrategyCardViewModel,
)


class _Trading(QObject):
    """Whether trading is on, and when that changes: what a host offers."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.enabled = False

    def set(self, enabled: bool) -> None:
        self.enabled = enabled
        self.changed.emit()


def _card(
    qtbot, market_type: MarketType = MarketType.FUTURES_USD_M
) -> tuple[StrategyCard, StrategyCardViewModel, _Trading]:
    strategy, trading = StrategyCardViewModel(), _Trading()
    strategy.set_strategy_options(
        [{"label": "EMA crossover", "key": "ema_crossover"}], ["1m", "5m"]
    )
    card = StrategyCard(
        StrategyCardBinding(
            strategy=strategy,
            is_trading_enabled=lambda: trading.enabled,
            trading_state_changed=trading.changed,
        ),
        market_type=market_type,
    )
    qtbot.addWidget(card)
    return card, strategy, trading


def _child[T: QWidget](card: StrategyCard, kind: type[T], name: str) -> T:
    child = card.findChild(kind, name)
    assert child is not None, name
    return child


def test_the_card_is_a_stock_group_box_with_no_style_of_its_own(qtbot) -> None:
    card, _, _ = _card(qtbot)

    assert isinstance(card, QGroupBox)
    assert card.title() == "Strategy"
    assert card.styleSheet() == ""
    for widget in card.findChildren(QWidget):
        assert widget.styleSheet() == "", widget.objectName()
        assert type(widget).__module__.startswith("PySide6"), type(widget)


@pytest.mark.parametrize(
    ("market_type", "shown"),
    [(MarketType.FUTURES_USD_M, True), (MarketType.SPOT, False)],
)
def test_leverage_is_offered_on_futures_only(qtbot, market_type, shown) -> None:
    card, _, _ = _card(qtbot, market_type)

    leverage = _child(card, QDoubleSpinBox, "spnLiveLeverage")

    assert not leverage.isHidden() is shown


def test_arm_and_disarm_reach_the_view_model(qtbot) -> None:
    card, strategy, _ = _card(qtbot)
    asked: list[str] = []
    strategy.armRequested.connect(lambda: asked.append("arm"))
    strategy.disarmRequested.connect(lambda: asked.append("disarm"))

    _child(card, QPushButton, "btnArmStrategy").click()
    _child(card, QPushButton, "btnDisarmStrategy").click()

    assert asked == ["arm", "disarm"]


def test_choosing_a_strategy_records_its_key_not_its_label(qtbot) -> None:
    card, strategy, _ = _card(qtbot)
    strategy.set_strategy_options(
        [
            {"label": "EMA crossover", "key": "ema_crossover"},
            {"label": "RSI", "key": "rsi"},
        ],
        ["1m"],
    )

    _child(card, QComboBox, "cboLiveStrategy").setCurrentIndex(1)

    assert strategy.selectedStrategyKey == "rsi"


def test_the_card_locks_while_trading_is_on_or_an_arm_is_in_flight(qtbot) -> None:
    card, strategy, trading = _card(qtbot)
    arm = _child(card, QPushButton, "btnArmStrategy")
    assert arm.isEnabled()

    trading.set(True)
    assert not arm.isEnabled()

    trading.set(False)
    strategy.set_armed_summary("", busy=True)
    assert not arm.isEnabled()


def test_the_armed_summary_is_said_in_words(qtbot) -> None:
    card, strategy, _ = _card(qtbot)
    summary = _child(card, QLabel, "lblArmedStrategy")
    assert summary.text() == "No strategy armed."

    strategy.set_armed_summary("EMA crossover on 1m", busy=False)

    assert summary.text() == "EMA crossover on 1m"
