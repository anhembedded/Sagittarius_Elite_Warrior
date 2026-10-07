from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.charting.timeframe_picker import (
    PinnedTimeframes,
    TimeframePickerDialog,
)
from Sagittarius_Elite_Warrior.src.support.charting.timeframe_picker import (
    all_options as all_timeframe_options,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from sagittarius_engine.extensions.pyside_mvc import BaseView

if TYPE_CHECKING:
    from .market_data_settings_view_model import MarketDataSettingsViewModel


class MarketDataSettingsView(BaseView):
    """@brief The Market Data page of Tools → Options (`EPIC-033E`)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model: MarketDataSettingsViewModel | None = None
        self._interval_picker: TimeframePickerDialog | None = None
        self._interval_picker_pinned = PinnedTimeframes()
        self._build_ui()

    def set_view_model(self, view_model: MarketDataSettingsViewModel) -> None:
        self._view_model = view_model

        self._default_symbols_field.setText(view_model.defaultSymbols)
        self._btn_default_interval.setText(view_model.defaultInterval)
        self._sync_days_spin.setValue(view_model.defaultSyncDays)
        self._apply_status(view_model.statusMessage, view_model.statusIsError)

        self._default_symbols_field.textEdited.connect(self._on_default_symbols_edited)
        self._sync_days_spin.valueChanged.connect(self._on_sync_days_changed)

        view_model.defaultSymbolsChanged.connect(
            lambda: self._default_symbols_field.setText(view_model.defaultSymbols)
        )
        view_model.defaultIntervalChanged.connect(
            lambda: self._btn_default_interval.setText(view_model.defaultInterval)
        )
        view_model.defaultSyncDaysChanged.connect(
            lambda: self._sync_days_spin.setValue(view_model.defaultSyncDays)
        )
        view_model.statusChanged.connect(
            lambda: self._apply_status(
                view_model.statusMessage, view_model.statusIsError
            )
        )

    def _on_default_symbols_edited(self, text: str) -> None:
        self._view_model.defaultSymbols = text

    def _on_default_interval_edited(self, text: str) -> None:
        self._view_model.defaultInterval = text

    def _on_sync_days_changed(self, value: int) -> None:
        self._view_model.defaultSyncDays = value

    def _apply_status(self, message: str, is_error: bool) -> None:
        prefix = "Error: " if is_error and message else ""
        self._status_label.setText(prefix + message)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        warning = plain_label(
            "Default Symbols/Interval/Sync Days are written to "
            "user_config.json. Data mode, the Market mode and historical "
            "backtests read the public mainnet; every trading desk and bot "
            "charts the market its own orders fill in."
        )
        warning.setObjectName("lblMarketDataSettingsWarning")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        defaults_box = QGroupBox("Defaults")
        defaults_form = QFormLayout(defaults_box)
        self._default_symbols_field = QLineEdit()
        self._default_symbols_field.setObjectName("txtDefaultSymbols")
        self._default_symbols_field.setPlaceholderText("BTCUSDT, ETHUSDT")
        defaults_form.addRow("Default Symbols:", self._default_symbols_field)

        self._btn_default_interval = QPushButton()
        self._btn_default_interval.setObjectName("btnDefaultInterval")
        self._btn_default_interval.clicked.connect(self._open_default_interval_picker)
        defaults_form.addRow("Default Interval:", self._btn_default_interval)

        self._sync_days_spin = QSpinBox()
        self._sync_days_spin.setObjectName("spinDefaultSyncDays")
        self._sync_days_spin.setRange(1, 3650)
        defaults_form.addRow("Default Sync Days:", self._sync_days_spin)
        layout.addWidget(defaults_box)

        self._status_label = plain_label()
        self._status_label.setObjectName("lblMarketDataSettingsStatus")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)
        layout.addStretch(1)

    def _open_default_interval_picker(self) -> None:
        if self._interval_picker is None:
            self._interval_picker = TimeframePickerDialog.from_callbacks(
                get_codes=lambda: [option.code for option in all_timeframe_options()],
                get_current=lambda: (
                    self._view_model.defaultInterval
                    if self._view_model is not None
                    else ""
                ),
                get_pinned=self._interval_picker_pinned.get,
                set_pinned=self._interval_picker_pinned.set,
                parent=self,
            )
            self._interval_picker.chosen.connect(self._on_default_interval_edited)
        self._interval_picker.open_dialog()
