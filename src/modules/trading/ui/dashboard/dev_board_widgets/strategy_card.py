"""`BOT-144` — the Dev Board's Strategy card, split out of
`dev_board_panel.py`. `EPIC-023C` — a real "Nạp chiến lược" card, driven by
the same `StrategyArmingCoordinator` instance `DashboardPresenter` owns.
Wiring mirrors `TradingView._build_strategy_card()` exactly — same fixed
domain terms, same objectNames.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    MAX_LEVERAGE,
    MAX_SIZING_PERCENT,
    MIN_LEVERAGE,
    MIN_SIZING_PERCENT,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.strategy_card_view_model import (
    StrategyCardViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import Palette
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    Panel,
    StyledButton,
    StyleRole,
)

from ..dashboard_view_model import DashboardQmlViewModel
from .layout_helpers import field_row, field_style, section_row

_PARAMS_BUTTON_TEXT = "Strategy Parameters…"
_ARM_TEXT = "Arm Strategy"
_DISARM_TEXT = "Disarm"
_NOT_ARMED_TEXT = "No strategy armed."


class StrategyCard(Panel):
    """Fully self-contained: reads only `view_model` (both
    `view_model.strategy` and `view_model.enabled` — the Enable/Disable
    toggle's own state — are reachable through the one `view_model`
    reference this card already holds, so no second collaborator is
    needed). `_sync_armed_summary()` disables the whole card while
    `strategyBusy` OR while trading is on (`EPIC-023D`) — the same
    pre-emptive, visible-before-click half of `EPIC-022` §4.1's rule
    `TradingView`'s own `_apply_armed_summary` enforces; the command
    handler refuses the swap server-side regardless either way. Subscribing
    to `view_model.tradingStateChanged` directly (rather than requiring
    `DevBoardPanel` to call back in after its own toggle handling) keeps
    this reaction owned by the card whose state it actually changes."""

    def __init__(
        self, view_model: DashboardQmlViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        # `DashboardQmlViewModel.strategy` is a PySide6 `@Property`; mypy
        # reads the descriptor itself (`Property`) rather than the
        # `StrategyCardViewModel` it actually holds at runtime — the same
        # systemic false positive `pyproject.toml`'s `[tool.mypy]` exclude
        # list documents for `presentation/` (needs a stub/plugin decision,
        # not a per-line fix). Narrowed once here rather than ignored at
        # every call site below.
        self._strategy_vm: StrategyCardViewModel = view_model.strategy  # type: ignore[assignment]
        layout = self.body_layout
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addLayout(section_row("Strategy"))

        self._cbo_live_strategy = QComboBox()
        self._cbo_live_strategy.setObjectName("cboLiveStrategy")
        self._cbo_live_strategy.setFixedHeight(32)
        self._cbo_live_strategy.setStyleSheet(field_style())
        layout.addWidget(field_row("Strategy", self._cbo_live_strategy))

        self._cbo_live_interval = QComboBox()
        self._cbo_live_interval.setObjectName("cboLiveInterval")
        self._cbo_live_interval.setFixedHeight(32)
        self._cbo_live_interval.setStyleSheet(field_style())
        layout.addWidget(field_row("Timeframe", self._cbo_live_interval))

        self._spn_sizing_percent = QDoubleSpinBox()
        self._spn_sizing_percent.setObjectName("spnLiveSizingPercent")
        self._spn_sizing_percent.setRange(MIN_SIZING_PERCENT, MAX_SIZING_PERCENT)
        self._spn_sizing_percent.setSingleStep(1.0)
        self._spn_sizing_percent.setSuffix(" %")
        self._spn_sizing_percent.setFixedHeight(32)
        self._spn_sizing_percent.setStyleSheet(field_style())
        layout.addWidget(field_row("% Capital/Trade", self._spn_sizing_percent))

        self._spn_leverage = QDoubleSpinBox()
        self._spn_leverage.setObjectName("spnLiveLeverage")
        self._spn_leverage.setRange(MIN_LEVERAGE, MAX_LEVERAGE)
        self._spn_leverage.setSingleStep(1.0)
        self._spn_leverage.setSuffix(" x")
        self._spn_leverage.setFixedHeight(32)
        self._spn_leverage.setStyleSheet(field_style())
        layout.addWidget(field_row("Leverage", self._spn_leverage))

        self._btn_strategy_params = StyledButton(
            _PARAMS_BUTTON_TEXT, role=StyleRole.SECONDARY_BUTTON
        )
        self._btn_strategy_params.setObjectName("btnStrategyParams")
        self._btn_strategy_params.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self._btn_strategy_params)

        actions = QWidget()
        actions_row = QHBoxLayout(actions)
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(8)
        self._btn_arm_strategy = StyledButton(_ARM_TEXT, role=StyleRole.PRIMARY_BUTTON)
        self._btn_arm_strategy.setObjectName("btnArmStrategy")
        self._btn_arm_strategy.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_disarm_strategy = StyledButton(
            _DISARM_TEXT, role=StyleRole.SECONDARY_BUTTON
        )
        self._btn_disarm_strategy.setObjectName("btnDisarmStrategy")
        self._btn_disarm_strategy.setCursor(Qt.CursorShape.PointingHandCursor)
        actions_row.addWidget(self._btn_arm_strategy, 1)
        actions_row.addWidget(self._btn_disarm_strategy, 1)
        layout.addWidget(actions)

        self._lbl_armed_strategy = QLabel(_NOT_ARMED_TEXT)
        self._lbl_armed_strategy.setObjectName("lblArmedStrategy")
        self._lbl_armed_strategy.setWordWrap(True)
        layout.addWidget(self._lbl_armed_strategy)

        #: Everything above is disabled while an arm/disarm is in flight, or
        #: while trading is enabled — see the class docstring for what this
        #: does NOT yet gate on.
        self._strategy_controls = (
            self._cbo_live_strategy,
            self._cbo_live_interval,
            self._spn_sizing_percent,
            self._spn_leverage,
            self._btn_strategy_params,
            self._btn_arm_strategy,
            self._btn_disarm_strategy,
        )

        self._cbo_live_strategy.currentIndexChanged.connect(
            lambda _index: self._strategy_vm.requestStrategySelection(
                self._cbo_live_strategy.currentData() or ""
            )
        )
        self._cbo_live_interval.currentTextChanged.connect(
            self._strategy_vm.requestIntervalSelection
        )
        self._spn_sizing_percent.valueChanged.connect(
            self._strategy_vm.requestSizingPercent
        )
        self._spn_leverage.valueChanged.connect(self._strategy_vm.requestLeverage)
        self._btn_arm_strategy.clicked.connect(self._strategy_vm.requestArm)
        self._btn_disarm_strategy.clicked.connect(self._strategy_vm.requestDisarm)
        self._btn_strategy_params.clicked.connect(self._open_strategy_params_dialog)

        self._strategy_vm.strategyConfigChanged.connect(
            self._on_strategy_config_changed
        )
        view_model.tradingStateChanged.connect(self._sync_armed_summary)
        self._sync_strategy_options()
        self._sync_strategy_selection()
        self._sync_armed_summary()

    def _open_strategy_params_dialog(self) -> None:
        """Built fresh per opening — same reasoning `TradingView`'s own
        method documents. Imported lazily for the same reason: the dialog
        pulls in `QScrollArea`/`Overlay` chrome no user who never opens it
        should pay for at card construction. Parented to `self.window()`
        — the window behind whichever dock the workbench put this card in,
        a valid parent even before the card is placed anywhere (`window()`
        then answers the card itself, same fallback
        `dev_board_panel.py`'s own `_dialog_parent()` documents)."""
        from Sagittarius_Elite_Warrior.src.support.ui_kit.param_form import (
            StrategyParamsDialog,
        )

        # `BotParamsSink.botParamsError`/`.botParamsGroups` are plain
        # settable attributes on the Protocol; `StrategyCardViewModel`
        # implements both as PySide6 `@Property` (read-only to mypy, which
        # reads the descriptor as `Property` rather than the runtime value)
        # — the same systemic false positive, one structural check deeper.
        dialog = StrategyParamsDialog(self._strategy_vm, self.window())  # type: ignore[arg-type]
        dialog.exec()

    def _on_strategy_config_changed(self) -> None:
        self._sync_strategy_options()
        self._sync_strategy_selection()
        self._sync_armed_summary()

    def _sync_strategy_options(self) -> None:
        """@details Each row's registry key rides on `setItemData`, never
        on the visible text — same reasoning `TradingView`'s own method
        documents (a renamed strategy silently stops being armable
        otherwise)."""
        self._cbo_live_strategy.blockSignals(True)
        self._cbo_live_strategy.clear()
        # `strategyOptions`/`intervalOptions`/`liveInterval`/`sizingPercent`/
        # `leverage`/`armedSummary` below are themselves each a PySide6
        # `@Property` on `StrategyCardViewModel` — narrowing `self._strategy_vm`
        # (see `__init__`) resolves the outer object's own type but not each
        # inner `@Property` field's, the same systemic false positive one
        # level deeper.
        for option in self._strategy_vm.strategyOptions:  # type: ignore[attr-defined]
            self._cbo_live_strategy.addItem(
                option.get("label", ""), option.get("key", "")
            )
        self._cbo_live_strategy.blockSignals(False)

        self._cbo_live_interval.blockSignals(True)
        self._cbo_live_interval.clear()
        self._cbo_live_interval.addItems(self._strategy_vm.intervalOptions)  # type: ignore[arg-type]
        self._cbo_live_interval.blockSignals(False)

    def _sync_strategy_selection(self) -> None:
        vm = self._strategy_vm
        self._cbo_live_strategy.blockSignals(True)
        index = self._cbo_live_strategy.findData(vm.selectedStrategyKey)
        if index >= 0:
            self._cbo_live_strategy.setCurrentIndex(index)
        self._cbo_live_strategy.blockSignals(False)

        self._cbo_live_interval.blockSignals(True)
        if vm.liveInterval:
            self._cbo_live_interval.setCurrentText(vm.liveInterval)  # type: ignore[arg-type]
        self._cbo_live_interval.blockSignals(False)

        for spin, value in (
            (self._spn_sizing_percent, vm.sizingPercent),
            (self._spn_leverage, vm.leverage),
        ):
            spin.blockSignals(True)
            spin.setValue(value)  # type: ignore[arg-type]
            spin.blockSignals(False)

    def _sync_armed_summary(self) -> None:
        vm = self._strategy_vm
        summary = vm.armedSummary
        self._lbl_armed_strategy.setText(summary or _NOT_ARMED_TEXT)  # type: ignore[arg-type]
        self._lbl_armed_strategy.setStyleSheet(
            f"color: {Palette.SUCCESS if summary else Palette.MUTED}; font-size: 11px;"
        )
        editable = not vm.strategyBusy and not self._view_model.enabled
        for widget in self._strategy_controls:
            widget.setEnabled(editable)
