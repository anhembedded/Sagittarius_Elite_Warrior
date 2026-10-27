"""`EPIC-047D` — the fields of one connection profile, and the profile they read as.

A form of stock controls: it shows a `LinkProfile` (`show`) and reads one back (`read`); it keeps no
profile of its own and never validates (the page asks `problem_of`). Every edit calls the listener
once. The reconnect factor is not a field: it is carried through from the profile shown.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    DEFAULT_USER,
    PORT_MAX,
    KeySource,
    LinkProfile,
    LinkProtocol,
    ReconnectPolicy,
)
from Sagittarius_Elite_Warrior.src.shell.link_options import link_options_words as words
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

_SECONDS_MAX = 3600.0
_TIMEOUT_MIN_S = 0.1


class ProfileForm(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("options::link::form")
        self._listener: Callable[[], None] = lambda: None
        self._loading = False
        self._shown = LinkProfile(name="", host="")
        self._name = self._line("name")
        self._host = self._line("host")
        self._port = QSpinBox()
        self._port.setRange(1, PORT_MAX)
        self._user = self._line("user")
        self._protocol = QComboBox()
        for protocol in LinkProtocol:
            self._protocol.addItem(
                words.PROTOCOL_TEXT.get(protocol.value, protocol.value), protocol.value
            )
        self._known_hosts = self._line("known_hosts")
        self._known_hosts.setPlaceholderText(words.KNOWN_HOSTS_HINT)
        self._timeout = self._seconds()
        self._timeout.setMinimum(_TIMEOUT_MIN_S)
        self._attempts = QSpinBox()
        self._attempts.setRange(0, 1000)
        self._attempts.setSpecialValueText(words.ATTEMPTS_ANY)
        self._first_delay = self._seconds()
        self._max_delay = self._seconds()
        self._agent = QRadioButton(words.AGENT_TEXT)
        self._key_file_radio = QRadioButton(words.KEY_FILE_TEXT)
        self._key_file = self._line("key_file")
        self._browse = QPushButton(words.BROWSE_TEXT)
        self._name_the_controls()
        self._lay_out()
        self._connect_edits()

    def set_listener(self, listener: Callable[[], None]) -> None:
        self._listener = listener

    def show_profile(self, profile: LinkProfile) -> None:
        self._loading = True
        try:
            self._shown = profile
            self._name.setText(profile.name)
            self._host.setText(profile.host)
            self._port.setValue(profile.port)
            self._user.setText(profile.user)
            self._protocol.setCurrentIndex(
                self._protocol.findData(profile.protocol.value)
            )
            self._known_hosts.setText(profile.known_hosts)
            self._timeout.setValue(profile.connect_timeout_s)
            self._attempts.setValue(profile.reconnect.max_attempts or 0)
            self._first_delay.setValue(profile.reconnect.first_delay_s)
            self._max_delay.setValue(profile.reconnect.max_delay_s)
            self._agent.setChecked(profile.key_source is KeySource.AGENT)
            self._key_file_radio.setChecked(profile.key_source is KeySource.KEY_FILE)
            self._key_file.setText(profile.key_file)
            self._sync_key_enabled()
        finally:
            self._loading = False

    def read_profile(self) -> LinkProfile:
        use_file = self._key_file_radio.isChecked()
        return replace(
            self._shown,
            name=self._name.text(),
            host=self._host.text().strip(),
            port=self._port.value(),
            user=self._user.text().strip() or DEFAULT_USER,
            protocol=LinkProtocol(str(self._protocol.currentData())),
            key_source=KeySource.KEY_FILE if use_file else KeySource.AGENT,
            key_file=self._key_file.text().strip() if use_file else "",
            known_hosts=self._known_hosts.text().strip(),
            connect_timeout_s=self._timeout.value(),
            reconnect=ReconnectPolicy(
                first_delay_s=self._first_delay.value(),
                max_delay_s=self._max_delay.value(),
                factor=self._shown.reconnect.factor,
                max_attempts=self._attempts.value() or None,
            ),
        )

    # -- construction ---------------------------------------------------------------------

    def _line(self, name: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setObjectName(f"options::link::{name}")
        return edit

    def _seconds(self) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(0.0, _SECONDS_MAX)
        box.setDecimals(1)
        return box

    def _name_the_controls(self) -> None:
        for name, control in (
            ("port", self._port),
            ("protocol", self._protocol),
            ("timeout", self._timeout),
            ("attempts", self._attempts),
            ("first_delay", self._first_delay),
            ("max_delay", self._max_delay),
            ("agent", self._agent),
            ("key_file_radio", self._key_file_radio),
            ("browse", self._browse),
        ):
            control.setObjectName(f"options::link::{name}")

    def _lay_out(self) -> None:
        form = QFormLayout()
        for text, control in (
            (words.NAME_LABEL, self._name),
            (words.HOST_LABEL, self._host),
            (words.PORT_LABEL, self._port),
            (words.USER_LABEL, self._user),
            (words.PROTOCOL_LABEL, self._protocol),
            (words.KNOWN_HOSTS_LABEL, self._known_hosts),
            (words.TIMEOUT_LABEL, self._timeout),
            (words.ATTEMPTS_LABEL, self._attempts),
            (words.FIRST_DELAY_LABEL, self._first_delay),
            (words.MAX_DELAY_LABEL, self._max_delay),
        ):
            form.addRow(text, control)
        key = QGroupBox(words.KEY_GROUP)
        key_layout = QVBoxLayout(key)
        key_layout.addWidget(self._agent)
        file_row = QHBoxLayout()
        file_row.addWidget(self._key_file_radio)
        file_row.addWidget(self._key_file, 1)
        file_row.addWidget(self._browse)
        key_layout.addLayout(file_row)
        note = plain_label(words.KEY_NOTE)
        note.setWordWrap(True)
        key_layout.addWidget(note)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(form)
        layout.addWidget(key)
        layout.addStretch(1)

    def _connect_edits(self) -> None:
        group = QButtonGroup(self)
        group.addButton(self._agent)
        group.addButton(self._key_file_radio)
        for edit in (
            self._name,
            self._host,
            self._user,
            self._known_hosts,
            self._key_file,
        ):
            edit.textEdited.connect(self._edited)
        for spin in (self._port, self._attempts):
            spin.valueChanged.connect(self._edited)
        for decimal in (self._timeout, self._first_delay, self._max_delay):
            decimal.valueChanged.connect(self._edited)
        self._protocol.currentIndexChanged.connect(self._edited)
        self._agent.toggled.connect(self._key_source_edited)
        self._browse.clicked.connect(self._browse_for_key)

    def _edited(self, *_ignored: object) -> None:
        if not self._loading:
            self._listener()

    def _key_source_edited(self, _checked: bool) -> None:
        self._sync_key_enabled()
        self._edited()

    def _sync_key_enabled(self) -> None:
        use_file = self._key_file_radio.isChecked()
        self._key_file.setEnabled(use_file)
        self._browse.setEnabled(use_file)

    def _browse_for_key(self) -> None:
        chosen, _filter = QFileDialog.getOpenFileName(self, words.BROWSE_TITLE)
        if chosen:
            self._key_file.setText(chosen)
            self._edited()
