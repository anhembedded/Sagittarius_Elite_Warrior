from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.timeframe_picker import (
    PinnedTimeframes,
    TimeframePickerDialog,
)
from Sagittarius_Elite_Warrior.src.support.charting.timeframe_picker import (
    all_options as all_timeframe_options,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    StyledButton,
    StyledField,
    StyleRole,
    apply_role,
    semantic_colour,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

if TYPE_CHECKING:
    from .market_data_settings_view_model import MarketDataSettingsViewModel

_FIELD_HEIGHT = 34

_MARKET_DATA_VENUE_LABELS = EnumLabels(
    MarketDataVenue,
    {
        MarketDataVenue.MAINNET_PUBLIC: "Mainnet — real, public prices (mainnet_public)",
        MarketDataVenue.FUTURES_TESTNET: "Futures Testnet — testnet prices (futures_testnet)",
    },
)


def _apply_tone(label: QLabel, name: str) -> None:
    """Colours `label` by a semantic tone chosen per instance at runtime —
    `kit/style.py`'s documented escape hatch for what `apply_role()` cannot
    express (a status message's colour depends on the outcome, not on what
    the widget structurally is). `QPalette`, never `setStyleSheet()`: the
    same idiom `ws_status_pill.py` established post-ADR-D21."""
    palette = QPalette(label.palette())
    palette.setColor(QPalette.ColorRole.WindowText, QColor(semantic_colour(name)))
    label.setPalette(palette)


class MarketDataSettingsView(BaseView):
    """@brief The Market Data settings section — one `SETTINGS_SECTION` contribution."""

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
        self._apply_venue(view_model.marketDataVenue)

        self._default_symbols_field.textEdited.connect(self._on_default_symbols_edited)
        self._sync_days_spin.valueChanged.connect(self._on_sync_days_changed)
        self._save_button.clicked.connect(view_model.requestSave)
        self._market_data_venue_combo.currentIndexChanged.connect(
            lambda _index: view_model.requestMarketDataVenue(
                self._market_data_venue_combo.currentData() or ""
            )
        )

        view_model.venueChanged.connect(
            lambda: self._apply_venue(view_model.marketDataVenue)
        )
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
        self._status_label.setText(message)
        _apply_tone(self._status_label, "danger" if is_error else "success")

    def _apply_venue(self, market_data_venue: str) -> None:
        index = self._market_data_venue_combo.findData(market_data_venue)
        self._market_data_venue_combo.blockSignals(True)
        if index >= 0:
            self._market_data_venue_combo.setCurrentIndex(index)
        self._market_data_venue_combo.blockSignals(False)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        warning = QLabel(
            "Default Symbols/Interval/Sync Days are written to "
            "user_config.json. Data Source requires an app restart to take "
            "effect — it is only read once, on app startup."
        )
        warning.setObjectName("lblMarketDataSettingsWarning")
        warning.setWordWrap(True)
        apply_role(warning, StyleRole.CAPTION)
        layout.addWidget(warning)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        row = 0
        grid.addWidget(QLabel("Data Source (chart):"), row, 0)
        self._market_data_venue_combo = QComboBox()
        self._market_data_venue_combo.setObjectName("cboMarketDataVenue")
        for venue in MarketDataVenue:
            self._market_data_venue_combo.addItem(
                _MARKET_DATA_VENUE_LABELS[venue], venue.value
            )
        grid.addWidget(self._market_data_venue_combo, row, 1)
        row += 1

        grid.addWidget(QLabel("Default Symbols:"), row, 0)
        row = self._add_default_symbols_row(grid, row)

        row = self._add_default_interval_row(grid, row)
        self._add_sync_days_row(grid, row)

        self._status_label = QLabel()
        self._status_label.setObjectName("lblMarketDataSettingsStatus")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._save_button = StyledButton("Save", role=StyleRole.PRIMARY_BUTTON)
        self._save_button.setObjectName("btnSaveMarketDataSettings")
        self._save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self._save_button, 0, Qt.AlignmentFlag.AlignLeft)

    def _add_default_symbols_row(self, grid: QGridLayout, row: int) -> int:
        field = StyledField()
        field.setObjectName("txtDefaultSymbols")
        field.setMinimumHeight(_FIELD_HEIGHT)
        field.setPlaceholderText("BTCUSDT, ETHUSDT")
        grid.addWidget(field, row, 1)
        self._default_symbols_field = field
        return row + 1

    def _add_default_interval_row(self, grid: QGridLayout, row: int) -> int:
        grid.addWidget(QLabel("Default Interval:"), row, 0)
        self._btn_default_interval = StyledButton("", role=StyleRole.SECONDARY_BUTTON)
        self._btn_default_interval.setObjectName("btnDefaultInterval")
        self._btn_default_interval.setMinimumHeight(_FIELD_HEIGHT)
        self._btn_default_interval.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_default_interval.clicked.connect(self._open_default_interval_picker)
        grid.addWidget(self._btn_default_interval, row, 1)
        return row + 1

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

    def _add_sync_days_row(self, grid: QGridLayout, row: int) -> int:
        grid.addWidget(QLabel("Default Sync Days:"), row, 0)
        self._sync_days_spin = QSpinBox()
        self._sync_days_spin.setObjectName("spinDefaultSyncDays")
        self._sync_days_spin.setRange(1, 3650)
        self._sync_days_spin.setFixedWidth(130)
        self._sync_days_spin.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        grid.addWidget(self._sync_days_spin, row, 1, Qt.AlignmentFlag.AlignLeft)
        return row + 1
