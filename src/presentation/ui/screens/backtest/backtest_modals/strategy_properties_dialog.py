"""Backtest strategy properties -- the four-tab dialog (BOT-104)."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
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

from ..logic.broker_properties_schema import BROKER_PROPERTY_FIELDS
from ._bot_param_field import _BotParamFieldWidget
from ._layout import _ACCENT, _field_row, _section_header

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


@dataclass(frozen=True)
class _WidgetBinding:
    """How to read a broker-property widget's current value, and how to
    write a value back into it — one instance per `BrokerPropertyField.key`
    (BUG-064). `read`/`write` close over the actual widget, so the binding
    table itself never needs a widget-type `isinstance` check at call time;
    that dispatch happens once, in whichever `_*_binding()` factory built it.
    """

    read: Callable[[], Any]
    write: Callable[[Any], None]


def _line_edit_binding(widget: QLineEdit) -> _WidgetBinding:
    return _WidgetBinding(widget.text, lambda value: widget.setText(str(value)))


def _spin_box_binding(widget: QSpinBox) -> _WidgetBinding:
    return _WidgetBinding(widget.value, lambda value: widget.setValue(int(value)))


def _check_box_binding(widget: QCheckBox) -> _WidgetBinding:
    return _WidgetBinding(
        widget.isChecked, lambda value: widget.setChecked(value is True)
    )


def _combo_box_data_binding(widget: QComboBox) -> _WidgetBinding:
    """For combos populated via `addItem(display_text, data)` — order size
    type, commission type — where the payload carries the `data`, not the
    visible label."""

    def write(value: Any) -> None:
        index = widget.findData(value)
        if index >= 0:
            widget.setCurrentIndex(index)

    return _WidgetBinding(widget.currentData, write)


def _field_names(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """The declared field names in `botParamsRows`, in order — the part of the
    schema that decides whether the Inputs tab's widgets must be rebuilt
    (BUG-064). Values are deliberately not part of this."""
    return [
        str(row.get("field", {}).get("name", ""))
        for row in rows
        if row.get("rowType") == "field"
    ]


def _combo_box_text_binding(widget: QComboBox) -> _WidgetBinding:
    """For combos populated via plain `addItems(labels)` — currency — where
    the payload carries the visible label itself."""

    def write(value: Any) -> None:
        index = widget.findText(str(value))
        if index >= 0:
            widget.setCurrentIndex(index)

    return _WidgetBinding(widget.currentText, write)


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
        self._property_bindings = self._build_property_bindings()
        self._wire_line_edits_to_save_on_focus_lost(self._properties_tab)
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
        self._prop_order_size_type = QComboBox()
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
        self._prop_commission_type = QComboBox()
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

    def _build_property_bindings(self) -> dict[str, _WidgetBinding]:
        """One row per `BrokerPropertyField.key` (BUG-064): the single place
        that says which widget backs a given property and how to read/write
        it, used by both `_collect_payload()` (widgets -> payload) and
        `_sync_properties()` (ViewModel -> widgets) instead of each hardcoding
        its own `.text()`/`.currentData()`/`.value()`/`.isChecked()` calls."""
        return {
            "initial_capital": _line_edit_binding(self._prop_initial_capital),
            "currency": _combo_box_text_binding(self._prop_currency),
            "order_size_type": _combo_box_data_binding(self._prop_order_size_type),
            "order_size_text": _line_edit_binding(self._prop_order_size_value),
            "pyramiding": _spin_box_binding(self._prop_pyramiding),
            "commission_type": _combo_box_data_binding(self._prop_commission_type),
            "commission_text": _line_edit_binding(self._prop_commission_value),
            "slippage_ticks": _spin_box_binding(self._prop_slippage_ticks),
            "long_leverage": _spin_box_binding(self._prop_long_leverage),
            "short_leverage": _spin_box_binding(self._prop_short_leverage),
            "take_profit_enabled": _check_box_binding(self._prop_take_profit_enabled),
            "take_profit_pct_text": _line_edit_binding(self._prop_take_profit_pct),
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
        self._wire_line_edits_to_save_on_focus_lost(self._inputs_tab)

    def _sync_properties(self) -> None:
        """Writes every current ViewModel value into its widget, driven by
        the same `BROKER_PROPERTY_FIELDS` schema `_collect_payload()` reads
        widgets against (BUG-064) — this used to hand-maintain its own combo
        index tables (`{"fixed_cash": 1, ...}`) in parallel with the literal
        `addItem()` order in `_build_properties_tab()`, which is exactly the
        kind of duplicate-declaration drift this whole schema exists to
        remove: `_combo_box_data_binding` looks the index up via
        `findData()` instead of assuming it."""
        vm = self._vm
        for field in BROKER_PROPERTY_FIELDS:
            self._property_bindings[field.key].write(getattr(vm, field.vm_attribute))
        self._prop_take_profit_pct.setEnabled(vm.takeProfitPctEnabled)

    def reset_all_fields(self) -> None:
        for field_widget in self._field_widgets:
            field_widget.reset_to_default()
        self._prop_initial_capital.setText("10000")
        self._prop_currency.setCurrentIndex(0)
        self._prop_order_size_type.setCurrentIndex(0)
        self._prop_order_size_value.setText("100")
        self._prop_pyramiding.setValue(1)
        self._prop_commission_type.setCurrentIndex(0)
        self._prop_commission_value.setText("0.1")
        self._prop_slippage_ticks.setValue(0)
        self._prop_long_leverage.setValue(1)
        self._prop_short_leverage.setValue(1)
        self._prop_take_profit_enabled.setChecked(False)
        self._prop_take_profit_pct.setText("2.0")

    def _wire_line_edits_to_save_on_focus_lost(self, root: QWidget) -> None:
        """BUG-064 — one generic pass instead of a one-off connection per
        field: every `QLineEdit` (including `_NumericStepLineEdit`, a
        subclass) under `root` gets its `editingFinished` wired to
        `_commit_edited_values()`. `editingFinished` fires on Return/Enter AND
        on losing focus — a bare `QLineEdit` with no connection at all does
        neither: a typed value lives only on the widget until something reads
        `.text()`, so it looked silently reverted the next time the dialog
        reopened and re-populated from the still-unchanged ViewModel.

        Deliberately NOT `save_and_close()`: losing focus must not close the
        backtest or close the dialog. See `_commit_edited_values()`.

        Applying this once per tab (here, and again in `_sync_inputs()` after
        every rebuild) means a field added to either tab later is wired for
        free — no new connection to remember to add alongside it.
        """
        for line_edit in root.findChildren(QLineEdit):
            line_edit.editingFinished.connect(self._commit_edited_values)

    def _collect_payload(self) -> dict:
        """The current value of every field in both tabs, in the shape the
        presenter's save/commit handlers expect. The only place either tab's
        widgets are read."""
        return {
            "inputs": {fw.field_name: fw.value() for fw in self._field_widgets},
            # BUG-064 — reads through the same `_property_bindings` table
            # `_sync_properties()` writes through; adding a new broker
            # property is one row in `_build_property_bindings()`, not a
            # hand-written `.text()`/`.value()`/`.isChecked()` call here too.
            "properties": {
                key: binding.read() for key, binding in self._property_bindings.items()
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
