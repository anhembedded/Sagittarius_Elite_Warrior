"""Backtest strategy properties -- the four-tab dialog (BOT-104)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Overlay,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit.widget_value import (
    connect_value_committed,
    mark_uses_item_data,
    read_widget_value,
    write_widget_value,
)

from ..logic.broker_properties_schema import BROKER_PROPERTY_FIELDS
from ._bot_param_field import _BotParamFieldWidget
from ._layout import _ACCENT, _field_row, _section_header

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


#: What "Đặt lại mặc định" restores each broker property to, keyed by the same
#: `BrokerPropertyField.key` everything else uses (BUG-064). A table rather
#: than twelve `setText`/`setValue`/`setChecked` calls, so a new property gets
#: its default declared in the one place the rest of it is already declared —
#: and so Reset can never drift from the widget list the way it silently could
#: when it named every widget by hand.
_BROKER_PROPERTY_DEFAULTS: dict[str, Any] = {
    "initial_capital": "10000",
    "currency": "USD",
    "order_size_type": "percent_of_equity",
    "order_size_text": "100",
    "pyramiding": 1,
    "commission_type": "percent",
    "commission_text": "0.1",
    "slippage_ticks": 0,
    "long_leverage": 1,
    "short_leverage": 1,
    "take_profit_enabled": False,
    "take_profit_pct_text": "2.0",
}


def _field_names(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """The declared field names in `botParamsRows`, in order — the part of the
    schema that decides whether the Inputs tab's widgets must be rebuilt
    (BUG-064). Values are deliberately not part of this."""
    return [
        str(row.get("field", {}).get("name", ""))
        for row in rows
        if row.get("rowType") == "field"
    ]


class StrategyPropertiesDialog(Overlay):
    """Port of `StrategyPropertiesModal.qml` (766 lines, BOT-104) — 4-tab
    dialog. Tabs 3/4 ("Định dạng"/"Hiển thị") were themselves QML
    placeholder text ("Sắp ra mắt" — Coming soon), ported as-is, not
    expanded."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("CÀI ĐẶT CHIẾN LƯỢC", parent=parent)
        self.setObjectName("botParamsDialog")
        self._vm = view_model
        self._strategy_name = ""
        self._field_widgets: list[_BotParamFieldWidget] = []
        self.resize(680, 620)

        self._tabs = QTabWidget()
        self.body_layout.addWidget(self._tabs)

        self._inputs_tab = QWidget()
        self._inputs_layout = QVBoxLayout(self._inputs_tab)
        self._inputs_layout.setObjectName("strategyInputsContent")
        self._inputs_layout.setSpacing(14)
        inputs_scroll = QScrollArea()
        inputs_scroll.setWidgetResizable(True)
        inputs_scroll.setFrameShape(QFrame.Shape.NoFrame)
        inputs_scroll.setWidget(self._inputs_tab)
        self._tabs.addTab(inputs_scroll, "Các đầu vào")

        self._properties_tab = self._build_properties_tab()
        self._property_widgets = self._build_property_widgets()
        self._wire_commit_on_edit(self._property_widgets.values())
        properties_scroll = QScrollArea()
        properties_scroll.setWidgetResizable(True)
        properties_scroll.setFrameShape(QFrame.Shape.NoFrame)
        properties_scroll.setWidget(self._properties_tab)
        self._tabs.addTab(properties_scroll, "Đặc tính")

        style_tab = QLabel("Hiển thị và màu sắc chỉ báo chiến lược (Sắp ra mắt)")
        style_tab.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 12px; padding: 12px;"
        )
        self._tabs.addTab(style_tab, "Định dạng")

        visibility_tab = QLabel("Bộ lọc hiển thị theo khung thời gian (Sắp ra mắt)")
        visibility_tab.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 12px; padding: 12px;"
        )
        self._tabs.addTab(visibility_tab, "Hiển thị")

        view_model.botParamsRowsChanged.connect(self._sync_inputs)
        view_model.botParamsSaved.connect(self.accept)

    # -- Tab 2: Properties ------------------------------------------------

    def _build_properties_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("strategyPropertiesContent")
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        layout.addLayout(_section_header("$", "Vốn ban đầu & tiền tệ"))
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        self._prop_initial_capital = QLineEdit()
        self._prop_initial_capital.setObjectName("propInitialCapital")
        row1.addLayout(_field_row("Vốn ban đầu", self._prop_initial_capital), 1)
        self._prop_currency = QComboBox()
        self._prop_currency.setObjectName("propCurrency")
        self._prop_currency.addItems(["USD", "USDT", "BTC", "VND"])
        row1.addLayout(_field_row("Đơn vị tiền tệ", self._prop_currency))
        layout.addLayout(row1)

        layout.addLayout(_section_header("#", "Kích thước lệnh & Pyramiding"))
        row2 = QHBoxLayout()
        row2.setSpacing(12)
        # Marked here, at the addItem(label, data) calls it applies to: this
        # combo's value is each item's data, not the Vietnamese label Qt's
        # USER property would otherwise report.
        self._prop_order_size_type = mark_uses_item_data(QComboBox())
        self._prop_order_size_type.setObjectName("propOrderSizeType")
        self._prop_order_size_type.addItem(
            "% Vốn cổ phần (Equity)", "percent_of_equity"
        )
        self._prop_order_size_type.addItem("USD Cố định (Cash)", "fixed_cash")
        self._prop_order_size_type.addItem("Hợp đồng / Coin", "fixed_contracts")
        row2.addLayout(_field_row("Loại kích thước lệnh", self._prop_order_size_type))
        self._prop_order_size_value = QLineEdit()
        self._prop_order_size_value.setObjectName("propOrderSizeValue")
        row2.addLayout(_field_row("Giá trị kích thước", self._prop_order_size_value), 1)
        self._prop_pyramiding = QSpinBox()
        self._prop_pyramiding.setObjectName("propPyramiding")
        self._prop_pyramiding.setRange(1, 10)
        row2.addLayout(_field_row("Kim tự tháp (Lệnh tối đa)", self._prop_pyramiding))
        layout.addLayout(row2)

        layout.addLayout(_section_header("%", "Hoa hồng & Trượt giá"))
        row3 = QHBoxLayout()
        row3.setSpacing(12)
        self._prop_commission_type = mark_uses_item_data(QComboBox())
        self._prop_commission_type.setObjectName("propCommissionType")
        self._prop_commission_type.addItem("% Giá trị lệnh", "percent")
        self._prop_commission_type.addItem("USD / Lệnh", "cash_per_order")
        self._prop_commission_type.addItem("USD / Hợp đồng", "cash_per_contract")
        row3.addLayout(_field_row("Loại hoa hồng", self._prop_commission_type))
        self._prop_commission_value = QLineEdit()
        self._prop_commission_value.setObjectName("propCommissionValue")
        row3.addLayout(_field_row("Mức hoa hồng", self._prop_commission_value), 1)
        self._prop_slippage_ticks = QSpinBox()
        self._prop_slippage_ticks.setObjectName("propSlippageTicks")
        self._prop_slippage_ticks.setRange(0, 100)
        row3.addLayout(_field_row("Trượt giá (Ticks)", self._prop_slippage_ticks))
        layout.addLayout(row3)

        layout.addLayout(_section_header("x", "Đòn bẩy (Leverage)"))
        row4 = QHBoxLayout()
        row4.setSpacing(12)
        self._prop_long_leverage = QSpinBox()
        self._prop_long_leverage.setObjectName("propLongLeverage")
        self._prop_long_leverage.setRange(1, 125)
        row4.addLayout(_field_row("Đòn bẩy Long (x)", self._prop_long_leverage), 1)
        self._prop_short_leverage = QSpinBox()
        self._prop_short_leverage.setObjectName("propShortLeverage")
        self._prop_short_leverage.setRange(1, 125)
        row4.addLayout(_field_row("Đòn bẩy Short (x)", self._prop_short_leverage), 1)
        layout.addLayout(row4)

        layout.addLayout(_section_header("%", "Chốt lời tự động (Take Profit %)"))
        row5 = QHBoxLayout()
        row5.setSpacing(12)
        self._prop_take_profit_enabled = QCheckBox("Bật Take Profit %")
        self._prop_take_profit_enabled.setObjectName("propTakeProfitEnabled")
        self._prop_take_profit_enabled.setStyleSheet(f"color: {Palette.TEXT_PRIMARY};")
        row5.addWidget(self._prop_take_profit_enabled)
        self._prop_take_profit_pct = QLineEdit()
        self._prop_take_profit_pct.setObjectName("propTakeProfitPct")
        self._prop_take_profit_enabled.toggled.connect(
            self._prop_take_profit_pct.setEnabled
        )
        row5.addLayout(
            _field_row(
                "% Chốt lời (khớp take_profit_percent của strategy)",
                self._prop_take_profit_pct,
            ),
            1,
        )
        layout.addLayout(row5)

        layout.addStretch(1)
        return tab

    def _build_property_widgets(self) -> dict[str, QWidget]:
        """Which widget backs each `BrokerPropertyField.key` — and only that
        (BUG-064).

        There is no read/write logic left here: `kit.widget_value` gets a
        widget's value out of Qt's own USER property metadata, so this stopped
        needing five per-widget-type binding constructors. Adding a broker
        property is one row here plus one in `BROKER_PROPERTY_FIELDS`; nothing
        has to be taught how to read a spin box.
        """
        return {
            "initial_capital": self._prop_initial_capital,
            "currency": self._prop_currency,
            "order_size_type": self._prop_order_size_type,
            "order_size_text": self._prop_order_size_value,
            "pyramiding": self._prop_pyramiding,
            "commission_type": self._prop_commission_type,
            "commission_text": self._prop_commission_value,
            "slippage_ticks": self._prop_slippage_ticks,
            "long_leverage": self._prop_long_leverage,
            "short_leverage": self._prop_short_leverage,
            "take_profit_enabled": self._prop_take_profit_enabled,
            "take_profit_pct_text": self._prop_take_profit_pct,
        }

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        btn_reset = QPushButton("Đặt lại mặc định")
        btn_reset.setObjectName("btnResetBotParams")
        btn_reset.clicked.connect(self.reset_all_fields)
        row.addWidget(btn_reset)
        row.addStretch(1)
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setObjectName("btnBotParamsCancel")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)
        # BUG-064 — was "Lưu & Chạy lại". Saving no longer starts a backtest,
        # so the old label promised something the button stopped doing.
        btn_save = QPushButton("Lưu")
        btn_save.setObjectName("btnBotParamsSave")
        btn_save.setStyleSheet(
            f"background-color: {_ACCENT}; color: {Palette.BG}; font-weight: bold; "
            f"border-radius: 6px; padding: 6px 14px;"
        )
        btn_save.clicked.connect(self.save_and_close)
        row.addWidget(btn_save)
        return row

    def open_for_strategy(self, strategy_name: str) -> None:
        self._strategy_name = strategy_name
        self.title = (
            f"CÀI ĐẶT CHIẾN LƯỢC: {strategy_name.upper()}"
            if strategy_name
            else "CÀI ĐẶT CHIẾN LƯỢC"
        )
        self._sync_inputs()
        self._sync_properties()
        self.show()
        self.raise_()

    def _sync_inputs(self) -> None:
        """Rebuilds the Inputs tab's widgets from the current schema.

        Skips the rebuild entirely when the schema still describes the SAME
        set of fields (BUG-064). Reason: committing an edit refreshes the
        schema so the stored values are current, which fires
        `botParamsRowsChanged` — and blindly rebuilding there would
        `deleteLater()` the very widget the user is typing in, mid-edit,
        every time they tab to the next field. Only the field *set* matters
        for whether widgets must be recreated; values are already correct in
        the live widgets (the user typed them), so a values-only change has
        nothing to rebuild. Switching strategies does change the field set,
        and still rebuilds.
        """
        rows = self._vm.botParamsRows
        if self._field_widgets and _field_names(rows) == [
            fw.field_name for fw in self._field_widgets
        ]:
            return

        while self._inputs_layout.count():
            item = self._inputs_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._field_widgets = []

        if not rows:
            empty = QLabel("Chiến lược này không có tham số đầu vào nào để cấu hình.")
            empty.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
            self._inputs_layout.addWidget(empty)
            return

        for row in rows:
            row_type = row.get("rowType", "")
            if row_type == "header":
                self._inputs_layout.addLayout(
                    _section_header("~", row.get("groupLabel", ""))
                )
            elif row_type == "field":
                field_widget = _BotParamFieldWidget(row.get("field", {}), self._vm)
                self._inputs_layout.addWidget(field_widget)
                self._field_widgets.append(field_widget)
        self._wire_commit_on_edit(fw.input_widget for fw in self._field_widgets)

    def _sync_properties(self) -> None:
        """Writes every current ViewModel value into its widget, driven by the
        same `BROKER_PROPERTY_FIELDS` schema `_collect_payload()` reads widgets
        against (BUG-064).

        This used to hand-maintain combo index tables (`{"fixed_cash": 1, ...}`)
        in parallel with the literal `addItem()` order in
        `_build_properties_tab()` — exactly the duplicate-declaration drift the
        schema exists to remove. `write_widget_value()` resolves the item by
        `findData()` instead of assuming a position.
        """
        vm = self._vm
        for field in BROKER_PROPERTY_FIELDS:
            write_widget_value(
                self._property_widgets[field.key], getattr(vm, field.vm_attribute)
            )
        self._prop_take_profit_pct.setEnabled(vm.takeProfitPctEnabled)

    def reset_all_fields(self) -> None:
        for field_widget in self._field_widgets:
            field_widget.reset_to_default()
        for key, value in _BROKER_PROPERTY_DEFAULTS.items():
            write_widget_value(self._property_widgets[key], value)

    def _wire_commit_on_edit(self, widgets: Iterable[QWidget]) -> None:
        """BUG-064 — auto-commit for EVERY kind of input, not just text boxes.

        `connect_value_committed()` (kit) picks the right signal from Qt's own
        metadata: `editingFinished` for free-text widgets (fires on Enter and
        on focus loss, never per keystroke), and the USER property's notify
        signal for widgets where changing the value IS the commit (check
        boxes, combos).

        The earlier version of this only ever scanned `findChildren(QLineEdit)`,
        so changing Pyramiding, Slippage, a leverage spin box, the Take Profit
        check box or either combo was silently dropped unless the user also
        clicked Save. Driving it from the declared widget list instead of a
        type-filtered child scan is what closes that gap for good.

        Deliberately NOT `save_and_close()`: losing focus must neither close
        the dialog nor start a run. See `_commit_edited_values()`.
        """
        for widget in widgets:
            connect_value_committed(widget, self._commit_edited_values)

    def _collect_payload(self) -> dict:
        """The current value of every field in both tabs, in the shape the
        presenter's save/commit handlers expect. The only place either tab's
        widgets are read."""
        return {
            "inputs": {fw.field_name: fw.value() for fw in self._field_widgets},
            "properties": {
                key: read_widget_value(widget)
                for key, widget in self._property_widgets.items()
            },
        }

    def _commit_edited_values(self) -> None:
        """Persist what is currently typed, and nothing more — the
        focus-loss/Enter path.

        BUG-064 went through two wrong versions of this before landing here,
        both reported by the user within minutes:

        1. Wired straight to the save path: tabbing between fields closed
           the dialog, because that path emits `botParamsSaved`, which
           `__init__` connects to `accept()` for the Save button's benefit.
        2. Wired to a wrapper that merely suppressed the close: the dialog
           stayed open, but the save still dispatched `RUN_REQUESTED`, so
           every field tabbed past moved the screen out of IDLE and kicked off
           a backtest — "chưa save sao lại nhảy state?".

        Both were the same mistake in different clothes: reusing the "save"
        pipeline for something that is not a save. The commit path is now its
        own signal end to end (`requestStrategyPropertiesCommit` ->
        `strategyPropertiesCommitRequested` ->
        `StrategyConfigCoordinator.commit_strategy_properties`), which
        validates and stores the values and stops there.
        """
        self._vm.requestStrategyPropertiesCommit(self._collect_payload())

    def save_and_close(self) -> None:
        """The "Lưu" button: persist and close the dialog (the close happens
        via `botParamsSaved` -> `accept`, so an invalid value leaves it open
        with the inline error showing).

        BUG-064 — this used to also start a backtest, which is why it was
        named `save_and_rerun` and labelled "Lưu & Chạy lại". Running is the
        user's decision, made with the Run button; the config change alone
        just marks any existing results stale.
        """
        self._vm.requestStrategyPropertiesSave(self._collect_payload())
