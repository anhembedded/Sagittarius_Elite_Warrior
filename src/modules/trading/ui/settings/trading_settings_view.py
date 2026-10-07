from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

if TYPE_CHECKING:
    from .trading_settings_view_model import TradingSettingsViewModel


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

        def edit_api_key(text: str) -> None:
            view_model.apiKey = text

        def edit_api_secret(text: str) -> None:
            view_model.apiSecret = text

        self._api_key_field.textEdited.connect(edit_api_key)
        self._api_secret_field.textEdited.connect(edit_api_secret)
        self._check_connection_button.clicked.connect(view_model.requestCheckConnection)

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

    def _apply_status(self, message: str, is_error: bool) -> None:
        self._status_label.setText(_worded(message, is_error))

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
        self._connection_result_label.setText(_worded(result_text, result_is_error))

    def _toggle_secret_reveal(self, checked: bool) -> None:
        self._api_secret_field.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        warning = QLabel(
            "API Key/Secret are written to secrets.local.json (not tracked "
            "in git). Every venue the key opens is on, and the next request to the "
            "exchange uses a key saved here."
        )
        warning.setObjectName("lblTradingSettingsWarning")
        warning.setWordWrap(True)
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
        grid.addWidget(self._credentials_source_label, row, 0, 1, 2)
        row += 1

        self._check_connection_button = QPushButton("Check Connection")
        self._check_connection_button.setObjectName("btnCheckConnection")
        grid.addWidget(self._check_connection_button, row, 0, 1, 2)
        row += 1

        self._connection_result_label = QLabel()
        self._connection_result_label.setObjectName("lblConnectionResult")
        self._connection_result_label.setWordWrap(True)
        grid.addWidget(self._connection_result_label, row, 0, 1, 2)
        row += 1

        self._status_label = QLabel()
        self._status_label.setObjectName("lblTradingSettingsStatus")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

    def _make_field(self, object_name: str) -> QLineEdit:
        field = QLineEdit()
        field.setObjectName(object_name)
        return field

    def _add_secret_row(self, grid: QGridLayout, row: int) -> int:
        grid.addWidget(QLabel("Binance API Secret (Private):"), row, 0)

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        self._api_secret_field = self._make_field("txtApiSecret")
        self._api_secret_field.setEchoMode(QLineEdit.EchoMode.Password)
        row_layout.addWidget(self._api_secret_field, 1)

        self._reveal_button = QCheckBox("Show secret")
        self._reveal_button.setObjectName("btnRevealSecret")
        self._reveal_button.toggled.connect(self._toggle_secret_reveal)
        row_layout.addWidget(self._reveal_button)

        grid.addWidget(row_widget, row, 1)
        return row + 1


def _worded(message: str, is_error: bool) -> str:
    """An error is named in words, never by weight or colour alone
    (`ui-presentation-rule.md` §1)."""
    return f"Error: {message}" if is_error and message else message
