from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import alerts_words
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.verb_confirmation import (
    VerbQuestion,
    ask_with_verbs,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

if TYPE_CHECKING:
    from .alerts_settings_view_model import AlertsSettingsViewModel

_INTRO = (
    "When a bot halts, the app tells you on Discord, even when you are away. "
    "Paste the channel's webhook URL and save it. A webhook is a secret: whoever "
    "has it can post in your channel, so it is kept in the operating system's "
    "keyring, never in a file or a log, and is not shown again once saved. Save, "
    "Remove and Send test act at once: OK and Apply have nothing to save here."
)

_REMOVE_QUESTION = VerbQuestion(
    title="Remove Discord Webhook",
    question="Remove the saved Discord webhook?",
    details=(
        "Alerts stop reaching Discord once the app restarts. You can paste the "
        "webhook again later."
    ),
    act="Remove webhook",
    keep="Keep webhook",
)


class AlertsSettingsView(BaseView):
    """@brief The Alerts page of Tools → Options (`EPIC-036D1`)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode_boxes: list[QComboBox] = []
        self._build_ui()

    def set_view_model(self, view_model: AlertsSettingsViewModel) -> None:
        self._save_button.clicked.connect(
            lambda: view_model.request_save(self._webhook_field.text())
        )
        self._webhook_field.returnPressed.connect(self._save_button.click)
        self._remove_button.clicked.connect(view_model.request_remove)
        self._test_button.clicked.connect(view_model.request_send_test)
        view_model.channel_changed.connect(lambda: self._apply_channel(view_model))
        view_model.working_changed.connect(lambda: self._apply_working(view_model))
        view_model.statusChanged.connect(lambda: self._apply_status(view_model))
        view_model.webhook_kept.connect(self._webhook_field.clear)
        view_model.bots_changed.connect(lambda: self._apply_bots(view_model))
        self._apply_bots(view_model)
        self._apply_channel(view_model)
        self._apply_working(view_model)
        self._apply_status(view_model)

    def confirm_removal(self) -> bool:
        """`True` when the owner chose to remove; keeping is the default."""
        return ask_with_verbs(self, _REMOVE_QUESTION)

    def _apply_channel(self, view_model: AlertsSettingsViewModel) -> None:
        self._channel_label.setText(view_model.channel_text)
        self._saved_label.setText(view_model.saved_text)
        self._apply_working(view_model)

    def _apply_working(self, view_model: AlertsSettingsViewModel) -> None:
        idle = not view_model.is_working
        self._working_label.setText(view_model.working_text)
        self._webhook_field.setEnabled(idle)
        self._save_button.setEnabled(idle)
        self._remove_button.setEnabled(idle and view_model.can_remove_webhook)
        self._test_button.setEnabled(idle and view_model.can_send_test)
        for box in self._mode_boxes:
            box.setEnabled(idle)

    def _apply_bots(self, view_model: AlertsSettingsViewModel) -> None:
        """Rebuilds the rows: one bot, one choice of what it may tell (`BOT-191`)."""
        while self._bots_form.rowCount():
            self._bots_form.removeRow(0)
        self._mode_boxes = []
        for row in view_model.bot_rows:
            box = QComboBox()
            box.setObjectName(f"cmbBotMode_{row.bot_id}")
            for mode, label in alerts_words.BOT_MODE_LABELS.items():
                box.addItem(label, mode.value)
            box.setCurrentIndex(box.findData(row.mode))
            box.setEnabled(not view_model.is_working)
            box.activated.connect(
                lambda _index, b=box, bot_id=row.bot_id: view_model.request_bot_mode(
                    bot_id, str(b.currentData())
                )
            )
            self._mode_boxes.append(box)
            self._bots_form.addRow(plain_label(row.name), box)
        self._bots_note.setText(view_model.bots_note)
        self._bots_note.setVisible(bool(view_model.bots_note))

    def _apply_status(self, view_model: AlertsSettingsViewModel) -> None:
        message = view_model.statusMessage
        # An error is named in words, never by weight or colour alone
        # (`ui-presentation-rule.md` §1).
        prefix = "Error: " if view_model.statusIsError and message else ""
        self._status_label.setText(prefix + message)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        intro = plain_label(_INTRO)
        intro.setObjectName("lblAlertsIntro")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        box = QGroupBox("Discord")
        box_layout = QVBoxLayout(box)

        self._channel_label = plain_label()
        self._channel_label.setObjectName("lblDiscordChannelState")
        self._channel_label.setWordWrap(True)
        box_layout.addWidget(self._channel_label)

        self._saved_label = plain_label()
        self._saved_label.setObjectName("lblDiscordSaved")
        box_layout.addWidget(self._saved_label)

        field_label = plain_label("Webhook URL:")
        self._webhook_field = QLineEdit()
        self._webhook_field.setObjectName("txtDiscordWebhook")
        self._webhook_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._webhook_field.setPlaceholderText("https://discord.com/api/webhooks/…")
        box_layout.addWidget(field_label)
        box_layout.addWidget(self._webhook_field)

        buttons = QHBoxLayout()
        self._save_button = QPushButton("Save")
        self._save_button.setObjectName("btnSaveDiscordWebhook")
        self._remove_button = QPushButton("Remove")
        self._remove_button.setObjectName("btnRemoveDiscordWebhook")
        self._test_button = QPushButton("Send test")
        self._test_button.setObjectName("btnSendDiscordTest")
        for button in (self._save_button, self._remove_button, self._test_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        box_layout.addLayout(buttons)
        layout.addWidget(box)

        bots_box = QGroupBox("Bots")
        bots_layout = QVBoxLayout(bots_box)
        bots_intro = plain_label(alerts_words.BOTS_INTRO)
        bots_intro.setObjectName("lblAlertsBotsIntro")
        bots_intro.setWordWrap(True)
        bots_layout.addWidget(bots_intro)
        self._bots_form = QFormLayout()
        bots_layout.addLayout(self._bots_form)
        self._bots_note = plain_label()
        self._bots_note.setObjectName("lblAlertsBotsNote")
        self._bots_note.setWordWrap(True)
        bots_layout.addWidget(self._bots_note)
        layout.addWidget(bots_box)

        self._working_label = plain_label()
        self._working_label.setObjectName("lblAlertsWorking")
        layout.addWidget(self._working_label)

        self._status_label = plain_label()
        self._status_label.setObjectName("lblAlertsStatus")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)
        layout.addStretch(1)
