"""Pure widget construction for `TradingView`'s Strategy card, split out of
`trading_view.py` to keep it under the file-length ceiling
(`architecture-rule.md` §5.4, `EPIC-027O`).

Wiring, sync and the `_strategy_controls` tuple stay on `TradingView`
itself — this only builds and labels the widgets its hand-rolled two-way
binding needs, mirroring what `dev_board_widgets/strategy_card.py` builds
for the same fields (that card is fully self-contained instead, since Dev
Board's binding style differs — see that file's own docstring).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    MAX_LEVERAGE,
    MAX_SIZING_PERCENT,
    MIN_LEVERAGE,
    MIN_SIZING_PERCENT,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    Card,
    StyledButton,
    StyleRole,
)

#: Domain terminology fixed by `ui-presentation-rule.md`: strategy
#: parameters are "Thông số Chiến lược", never the general Bot settings.
_PARAMS_BUTTON_TEXT = "Strategy Parameters…"
_ARM_TEXT = "Arm Strategy"
_DISARM_TEXT = "Disarm"
_NOT_ARMED_TEXT = "No strategy armed."


@dataclass(frozen=True)
class StrategyCardWidgets:
    """Every widget `TradingView` reaches for by name after construction."""

    card: QWidget
    strategy_combo: QComboBox
    interval_combo: QComboBox
    sizing_spin: QDoubleSpinBox
    leverage_label: QLabel
    leverage_spin: QDoubleSpinBox
    params_button: StyledButton
    arm_button: StyledButton
    disarm_button: StyledButton
    armed_label: QLabel


def build_strategy_card(field_label: Callable[[str], QLabel]) -> StrategyCardWidgets:
    """`field_label` is `TradingView._field_label` — the one shared
    `apply_role()` call site, passed in rather than duplicated here
    (`test_app_styling_only_shrinks.py` ratchets that call count)."""
    card = Card("STRATEGY")
    card.setObjectName("tradingStrategyCard")
    card.body_layout.setContentsMargins(12, 12, 12, 12)
    card.body_layout.setSpacing(8)

    card.body_layout.addWidget(field_label("Strategy"))
    strategy_combo = QComboBox()
    strategy_combo.setObjectName("cboLiveStrategy")
    card.body_layout.addWidget(strategy_combo)

    card.body_layout.addWidget(field_label("Trading Timeframe"))
    interval_combo = QComboBox()
    interval_combo.setObjectName("cboLiveInterval")
    card.body_layout.addWidget(interval_combo)

    card.body_layout.addWidget(field_label("% Capital per Trade"))
    sizing_spin = QDoubleSpinBox()
    sizing_spin.setObjectName("spnLiveSizingPercent")
    sizing_spin.setRange(MIN_SIZING_PERCENT, MAX_SIZING_PERCENT)
    sizing_spin.setSingleStep(1.0)
    sizing_spin.setSuffix(" %")
    card.body_layout.addWidget(sizing_spin)

    leverage_label = field_label("Leverage")
    card.body_layout.addWidget(leverage_label)
    leverage_spin = QDoubleSpinBox()
    leverage_spin.setObjectName("spnLiveLeverage")
    leverage_spin.setRange(MIN_LEVERAGE, MAX_LEVERAGE)
    leverage_spin.setSingleStep(1.0)
    leverage_spin.setSuffix(" x")
    card.body_layout.addWidget(leverage_spin)

    params_button = StyledButton(_PARAMS_BUTTON_TEXT, role=StyleRole.SECONDARY_BUTTON)
    params_button.setObjectName("btnStrategyParams")
    params_button.setCursor(Qt.CursorShape.PointingHandCursor)
    card.body_layout.addWidget(params_button)

    actions = QWidget()
    actions_row = QHBoxLayout(actions)
    actions_row.setContentsMargins(0, 0, 0, 0)
    actions_row.setSpacing(8)
    arm_button = StyledButton(_ARM_TEXT, role=StyleRole.PRIMARY_BUTTON)
    arm_button.setObjectName("btnArmStrategy")
    arm_button.setCursor(Qt.CursorShape.PointingHandCursor)
    disarm_button = StyledButton(_DISARM_TEXT, role=StyleRole.SECONDARY_BUTTON)
    disarm_button.setObjectName("btnDisarmStrategy")
    disarm_button.setCursor(Qt.CursorShape.PointingHandCursor)
    actions_row.addWidget(arm_button, 1)
    actions_row.addWidget(disarm_button, 1)
    card.body_layout.addWidget(actions)

    armed_label = QLabel(_NOT_ARMED_TEXT)
    armed_label.setObjectName("lblArmedStrategy")
    armed_label.setWordWrap(True)
    card.body_layout.addWidget(armed_label)

    return StrategyCardWidgets(
        card=card,
        strategy_combo=strategy_combo,
        interval_combo=interval_combo,
        sizing_spin=sizing_spin,
        leverage_label=leverage_label,
        leverage_spin=leverage_spin,
        params_button=params_button,
        arm_button=arm_button,
        disarm_button=disarm_button,
        armed_label=armed_label,
    )
