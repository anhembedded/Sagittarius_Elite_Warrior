from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    StyledButton,
    StyledField,
    StyleRole,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

if TYPE_CHECKING:
    from .trading_settings_view_model import TradingSettingsViewModel

_FIELD_HEIGHT = 34
#: Credentials are opaque strings a user compares character by character; a
#: monospace face is what makes that possible. Carried over from the
#: monolithic screen this section split off.
_FIELD_FONT_FAMILY = "Consolas"

#: `BOT-125` — carried over from the monolithic screen this section split off.
_VENUE_LOCKED_TEXT = (
    "Trading is active — disable trading on its desk "
    "before changing the trading venues."
)

#: `EPIC-028C` — one toggle per venue that can place orders; `DISABLED` has
#: none (nothing checked is trading off). A venue added to `TradingVenue`
#: with order submission needs a label here, or the view refuses to build
#: (`test_every_orderable_venue_has_a_toggle_label`).
_VENUE_TOGGLE_LABELS: dict[TradingVenue, str] = {
    TradingVenue.FUTURES_TESTNET: "Futures Testnet — simulated funds (futures_testnet)",
    TradingVenue.SPOT_TESTNET: "Spot Testnet — simulated funds (spot_testnet)",
}

_VENUES_HINT_TEXT = (
    "Nothing checked turns trading off. Each venue trades on its own desk."
)


class TradingSettingsView(BaseView):
    """@brief The Trading page of Tools → Options (`EPIC-033E`)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model: TradingSettingsViewModel | None = None
        self._build_ui()

    def set_view_model(self, view_model: TradingSettingsViewModel) -> None:
        self._view_model = view_model

        self._api_key_field.setText(view_model.apiKey)
        self._api_secret_field.setText(view_model.apiSecret)
        self._apply_status(view_model.statusMessage, view_model.statusIsError)
        self._apply_credentials_source(
            view_model.credentialsSourceLabel, view_model.credentialsLocked
        )
        self._apply_connection_check(
            view_model.connectionChecking,
            view_model.connectionResultText,
            view_model.connectionResultIsError,
        )
        self._apply_venues(view_model.enabledVenues, view_model.venueLocked)

        self._api_key_field.textEdited.connect(self._on_api_key_edited)
        self._api_secret_field.textEdited.connect(self._on_api_secret_edited)
        self._check_connection_button.clicked.connect(view_model.requestCheckConnection)
        for venue, toggle in self._venue_toggles.items():
            toggle.toggled.connect(
                lambda checked, value=venue.value: view_model.requestVenueEnabled(
                    value, checked
                )
            )

        view_model.venueChanged.connect(
            lambda: self._apply_venues(view_model.enabledVenues, view_model.venueLocked)
        )
        view_model.apiKeyChanged.connect(
            lambda: self._api_key_field.setText(view_model.apiKey)
        )
        view_model.apiSecretChanged.connect(
            lambda: self._api_secret_field.setText(view_model.apiSecret)
        )
        view_model.statusChanged.connect(
            lambda: self._apply_status(
                view_model.statusMessage, view_model.statusIsError
            )
        )
        view_model.credentialsSourceChanged.connect(
            lambda: self._apply_credentials_source(
                view_model.credentialsSourceLabel, view_model.credentialsLocked
            )
        )
        view_model.connectionCheckChanged.connect(
            lambda: self._apply_connection_check(
                view_model.connectionChecking,
                view_model.connectionResultText,
                view_model.connectionResultIsError,
            )
        )

    def _on_api_key_edited(self, text: str) -> None:
        self._view_model.apiKey = text

    def _on_api_secret_edited(self, text: str) -> None:
        self._view_model.apiSecret = text

    def _apply_status(self, message: str, is_error: bool) -> None:
        self._status_label.setText(message)
        color = Palette.DANGER if is_error else Palette.SUCCESS
        self._status_label.setStyleSheet(f"color: {color};")

    def _apply_credentials_source(self, label: str, locked: bool) -> None:
        """`EPIC-021B` §2.3 — when an environment variable is what is in
        effect, the fields are locked: an edit there would be silently
        ignored by `IExchangeCredentialsProvider.resolve()`."""
        self._credentials_source_label.setText(label)
        self._api_key_field.setReadOnly(locked)
        self._api_secret_field.setReadOnly(locked)

    def _apply_connection_check(
        self, checking: bool, result_text: str, result_is_error: bool
    ) -> None:
        self._check_connection_button.setEnabled(not checking)
        self._check_connection_button.setText(
            "Checking..." if checking else "Check Connection"
        )
        self._connection_result_label.setText(result_text)
        color = Palette.DANGER if result_is_error else Palette.SUCCESS
        self._connection_result_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _apply_venues(self, enabled_venues: list[str], locked: bool) -> None:
        for venue, toggle in self._venue_toggles.items():
            toggle.blockSignals(True)
            toggle.setChecked(venue.value in enabled_venues)
            toggle.blockSignals(False)
            toggle.setEnabled(not locked)
        self._venue_lock_label.setText(_VENUE_LOCKED_TEXT if locked else "")
        self._venue_lock_label.setVisible(locked)

    def _toggle_secret_reveal(self, checked: bool) -> None:
        self._api_secret_field.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        icon_name = "eye-off" if checked else "eye"
        self._reveal_button.setIcon(
            get_icon_loader().get_icon(icon_name, Palette.MUTED)
        )
        self._reveal_button.setToolTip("Hide secret" if checked else "Show secret")
        self._reveal_button.setAccessibleName(
            "Hide secret" if checked else "Show secret"
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        warning = QLabel(
            "API Key/Secret are written to secrets.local.json (not tracked "
            "in git). API Key/Secret and the trading venues both require an "
            "app restart to take effect — they are only read once, on app "
            "startup."
        )
        warning.setObjectName("lblTradingSettingsWarning")
        warning.setWordWrap(True)
        warning.setStyleSheet(f"color: {Palette.ACCENT}; font-size: 11px;")
        layout.addWidget(warning)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        row = 0
        grid.addWidget(QLabel("Binance API Key (Public):"), row, 0)
        self._api_key_field = self._make_field("txtApiKey")
        grid.addWidget(self._api_key_field, row, 1)
        row += 1

        row = self._add_secret_row(grid, row)

        self._credentials_source_label = QLabel()
        self._credentials_source_label.setObjectName("lblCredentialsSource")
        self._credentials_source_label.setWordWrap(True)
        self._credentials_source_label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 11px;"
        )
        grid.addWidget(self._credentials_source_label, row, 0, 1, 2)
        row += 1

        self._check_connection_button = StyledButton(
            "Check Connection", role=StyleRole.SECONDARY_BUTTON
        )
        self._check_connection_button.setObjectName("btnCheckConnection")
        self._check_connection_button.setCursor(Qt.CursorShape.PointingHandCursor)
        grid.addWidget(self._check_connection_button, row, 0, 1, 2)
        row += 1

        self._connection_result_label = QLabel()
        self._connection_result_label.setObjectName("lblConnectionResult")
        self._connection_result_label.setWordWrap(True)
        self._connection_result_label.setFont(QFont(_FIELD_FONT_FAMILY))
        grid.addWidget(self._connection_result_label, row, 0, 1, 2)
        row += 1

        row = self._add_venue_row(grid, row)

        self._status_label = QLabel()
        self._status_label.setObjectName("lblTradingSettingsStatus")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

    def _make_field(self, object_name: str) -> StyledField:
        field = StyledField()
        field.setObjectName(object_name)
        field.setMinimumHeight(_FIELD_HEIGHT)
        field.setFont(QFont(_FIELD_FONT_FAMILY))
        return field

    def _add_venue_row(self, grid: QGridLayout, row: int) -> int:
        grid.addWidget(QLabel("Trading venues:"), row, 0, Qt.AlignmentFlag.AlignTop)
        toggles_widget = QWidget()
        toggles_layout = QVBoxLayout(toggles_widget)
        toggles_layout.setContentsMargins(0, 0, 0, 0)
        self._venue_toggles: dict[TradingVenue, QCheckBox] = {}
        for venue in TradingVenue:
            if not venue.supports_order_submission:
                continue
            toggle = QCheckBox(_VENUE_TOGGLE_LABELS[venue])
            toggle.setObjectName(f"chkTradingVenue_{venue.value}")
            toggles_layout.addWidget(toggle)
            self._venue_toggles[venue] = toggle
        hint = QLabel(_VENUES_HINT_TEXT)
        hint.setObjectName("lblTradingVenuesHint")
        hint.setWordWrap(True)
        toggles_layout.addWidget(hint)
        grid.addWidget(toggles_widget, row, 1)
        row += 1

        self._venue_lock_label = QLabel()
        self._venue_lock_label.setObjectName("lblTradingVenueLocked")
        self._venue_lock_label.setWordWrap(True)
        self._venue_lock_label.setStyleSheet(
            f"color: {Palette.WARNING}; font-size: 11px;"
        )
        self._venue_lock_label.setVisible(False)
        grid.addWidget(self._venue_lock_label, row, 0, 1, 2)
        return row + 1

    def _add_secret_row(self, grid: QGridLayout, row: int) -> int:
        grid.addWidget(QLabel("Binance API Secret (Private):"), row, 0)

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        self._api_secret_field = self._make_field("txtApiSecret")
        self._api_secret_field.setEchoMode(QLineEdit.EchoMode.Password)
        row_layout.addWidget(self._api_secret_field, 1)

        self._reveal_button = QPushButton()
        self._reveal_button.setObjectName("btnRevealSecret")
        self._reveal_button.setCheckable(True)
        self._reveal_button.setFixedSize(36, 34)
        self._reveal_button.setIcon(get_icon_loader().get_icon("eye", Palette.MUTED))
        self._reveal_button.setToolTip("Show secret")
        self._reveal_button.setAccessibleName("Show secret")
        self._reveal_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._reveal_button.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.STATE_IDLE_BG}; "
            f"border: 1px solid {Palette.BORDER}; border-radius: 6px; }} "
            f"QPushButton:hover {{ background-color: {Palette.STATE_HOVER_BG}; }}"
        )
        self._reveal_button.toggled.connect(self._toggle_secret_reveal)
        row_layout.addWidget(self._reveal_button)

        grid.addWidget(row_widget, row, 1)
        return row + 1
