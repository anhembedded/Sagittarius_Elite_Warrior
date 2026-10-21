"""The Telegram group of the Alerts page (`EPIC-036D4`): the bot token (masked), the chat id,
Save and Remove, and two lines saying what is on and what is saved.

Stock controls only. The token field is a password field; the chat id is not a secret and is
shown. The page's view owns the working state and tells this group whether it is idle.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.telegram_settings_view_model import (
    TelegramSettingsViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label


class TelegramSettingsGroup(QGroupBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Telegram", parent)
        layout = QVBoxLayout(self)
        self._channel_label = plain_label()
        self._channel_label.setObjectName("lblTelegramChannelState")
        self._channel_label.setWordWrap(True)
        layout.addWidget(self._channel_label)
        self._saved_label = plain_label()
        self._saved_label.setObjectName("lblTelegramSaved")
        self._saved_label.setWordWrap(True)
        layout.addWidget(self._saved_label)

        self._token_field = QLineEdit()
        self._token_field.setObjectName("txtTelegramToken")
        self._token_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_field.setPlaceholderText("123456789:AA…")
        self._chat_field = QLineEdit()
        self._chat_field.setObjectName("txtTelegramChat")
        self._chat_field.setPlaceholderText("5550123, -1001234567890 or @channelname")
        layout.addWidget(plain_label("Bot token:"))
        layout.addWidget(self._token_field)
        layout.addWidget(plain_label("Chat id:"))
        layout.addWidget(self._chat_field)

        buttons = QHBoxLayout()
        self._save_button = QPushButton("Save")
        self._save_button.setObjectName("btnSaveTelegram")
        self._remove_button = QPushButton("Remove")
        self._remove_button.setObjectName("btnRemoveTelegram")
        buttons.addWidget(self._save_button)
        buttons.addWidget(self._remove_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self._can_remove = False

    def connect_view_model(self, view_model: TelegramSettingsViewModel) -> None:
        self._save_button.clicked.connect(
            lambda: view_model.request_save(
                self._token_field.text(), self._chat_field.text()
            )
        )
        self._chat_field.returnPressed.connect(self._save_button.click)
        self._remove_button.clicked.connect(view_model.request_remove)
        view_model.channel_changed.connect(lambda: self._show_channel(view_model))
        view_model.credentials_kept.connect(self._clear_fields)
        self._show_channel(view_model)

    def set_idle(self, idle: bool) -> None:
        """Nothing is being done: the fields and buttons may be used."""
        self._token_field.setEnabled(idle)
        self._chat_field.setEnabled(idle)
        self._save_button.setEnabled(idle)
        self._remove_button.setEnabled(idle and self._can_remove)

    def _show_channel(self, view_model: TelegramSettingsViewModel) -> None:
        self._channel_label.setText(view_model.channel_text)
        self._saved_label.setText(view_model.saved_text)
        self._can_remove = view_model.can_remove
        self._remove_button.setEnabled(
            self._save_button.isEnabled() and view_model.can_remove
        )

    def _clear_fields(self) -> None:
        self._token_field.clear()
        self._chat_field.clear()
