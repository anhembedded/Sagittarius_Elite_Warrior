from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView
from sagittarius_engine.extensions.pyside_mvc.widgets import (
    Panel,
    StyledButton,
    StyledField,
    StyleRole,
    apply_role,
)

if TYPE_CHECKING:
    from .settings_view_model import SettingsViewModel

#: SettingsScreen.qml's TextField/SpinBox backgrounds hardcoded their own
#: literal copies of these two colors rather than reading
#: Palette.STATE_IDLE_BG/STATE_HOVER_BG, even though the values are
#: identical — confirmed by comparing them directly. The QML file wasn't
#: touched to fix that (out of scope, kept unloaded on disk), but this
#: QtWidgets version has no reason to repeat the duplication.
_FIELD_BG = Palette.STATE_IDLE_BG
_FIELD_HOVER_BG = Palette.STATE_HOVER_BG

#: The two things `StyleRole.FIELD` deliberately has no opinion on, so they
#: are set through the widget API instead of a second stylesheet (EPIC-007F).
#: The height matches the reveal button beside the secret field, which is
#: `setFixedSize(36, 34)` — they must line up.
_FIELD_HEIGHT = 34
#: Credentials are opaque strings a user compares character by character;
#: a monospace face is what makes that possible. Carried over verbatim from
#: the QSS this replaced.
_FIELD_FONT_FAMILY = "Consolas"


class SettingsView(BaseView):
    """
    @brief The View for the API & Credentials screen — QtWidgets (EPIC-005D).

    @details
    Migrated off `QmlHostView`/`SettingsScreen.qml` (kept on disk, unloaded)
    per `EPIC-005`'s pilot: this screen's fields (plain text inputs, one
    spinbox, one reveal toggle) get tab-order, focus, and keyboard
    navigation for free from QtWidgets, where the QML version had to accept
    none of that or build it by hand.

    Wiring mirrors the QML version's two-way property binding by hand:
    `set_view_model()` connects each field's Qt Widget signal (`textEdited`,
    `valueChanged`) to the matching ViewModel property setter, and each
    ViewModel `*Changed` signal back to the widget's setter — the same
    "Python writes, UI shows; UI edits, Python holds" contract
    `SettingsViewModel`'s own docstring describes, now driven by native Qt
    signals instead of QML's implicit property bindings. `SettingsViewModel`
    and `SettingsPresenter` are unchanged: this migration is scoped to the
    rendering layer only.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model: SettingsViewModel | None = None
        self._build_ui()

    def set_view_model(self, view_model: SettingsViewModel) -> None:
        """Wires the view model two-way and loads its current field values.
        Mirrors QmlHostView.set_view_model()'s name/role so SettingsPresenter
        did not need to change."""
        self._view_model = view_model

        self._api_key_field.setText(view_model.apiKey)
        self._api_secret_field.setText(view_model.apiSecret)
        self._default_symbols_field.setText(view_model.defaultSymbols)
        self._default_interval_field.setText(view_model.defaultInterval)
        self._sync_days_spin.setValue(view_model.defaultSyncDays)
        self._apply_status(view_model.statusMessage, view_model.statusIsError)

        self._api_key_field.textEdited.connect(self._on_api_key_edited)
        self._api_secret_field.textEdited.connect(self._on_api_secret_edited)
        self._default_symbols_field.textEdited.connect(self._on_default_symbols_edited)
        self._default_interval_field.textEdited.connect(
            self._on_default_interval_edited
        )
        self._sync_days_spin.valueChanged.connect(self._on_sync_days_changed)
        self._save_button.clicked.connect(view_model.requestSave)

        view_model.apiKeyChanged.connect(
            lambda: self._api_key_field.setText(view_model.apiKey)
        )
        view_model.apiSecretChanged.connect(
            lambda: self._api_secret_field.setText(view_model.apiSecret)
        )
        view_model.defaultSymbolsChanged.connect(
            lambda: self._default_symbols_field.setText(view_model.defaultSymbols)
        )
        view_model.defaultIntervalChanged.connect(
            lambda: self._default_interval_field.setText(view_model.defaultInterval)
        )
        view_model.defaultSyncDaysChanged.connect(
            lambda: self._sync_days_spin.setValue(view_model.defaultSyncDays)
        )
        view_model.statusChanged.connect(
            lambda: self._apply_status(
                view_model.statusMessage, view_model.statusIsError
            )
        )

    # ------------------------------------------------------------------ #
    # Widget <-> ViewModel edit handlers (the "UI edits, Python holds" half)
    # ------------------------------------------------------------------ #

    def _on_api_key_edited(self, text: str) -> None:
        self._view_model.apiKey = text

    def _on_api_secret_edited(self, text: str) -> None:
        self._view_model.apiSecret = text

    def _on_default_symbols_edited(self, text: str) -> None:
        self._view_model.defaultSymbols = text

    def _on_default_interval_edited(self, text: str) -> None:
        self._view_model.defaultInterval = text

    def _on_sync_days_changed(self, value: int) -> None:
        self._view_model.defaultSyncDays = value

    def _apply_status(self, message: str, is_error: bool) -> None:
        self._status_label.setText(message)
        color = Palette.DANGER if is_error else Palette.SUCCESS
        self._status_label.setStyleSheet(f"color: {color};")

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

    # ------------------------------------------------------------------ #
    # Layout — mirrors SettingsScreen.qml's structure (kept on disk,
    # unloaded) field-for-field, so this migration changes nothing visible.
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        # Scoped to this class, not written bare. A bare property list is
        # Qt's universal selector, so the screen background would repaint
        # every descendant that has no rule of its own — the whole of
        # `BUG-008`, on the widget that contains the entire screen.
        self.setStyleSheet(
            f"{type(self).__name__} {{ background-color: {Palette.BG}; }}"
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        scroll.setWidget(content)

        # A bare Panel, not Card: this screen's header (icon, two-line
        # title/subtitle, its own BG_CARD_HEADER band) is materially richer
        # than Card's built-in title-label + header_actions row, so it stays
        # hand-built and goes into Panel's plain body_layout rather than
        # fighting Card's own header slot for a second one (EPIC-007F).
        card = Panel()
        content_layout.addWidget(card)
        card.body_layout.setContentsMargins(0, 0, 0, 0)
        card.body_layout.setSpacing(0)

        card.body_layout.addWidget(self._build_header())
        card.body_layout.addWidget(self._build_body())

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("settingsCardHeader")
        header.setFixedHeight(56)
        # Scoped by objectName rather than left bare, for the same reason as
        # the screen background above: unscoped, this band's colour and
        # border would cascade onto the icon, title, subtitle and Save
        # button it contains. Kept hand-written rather than given a
        # `StyleRole` — a card header band with its own top-corner radii is
        # one screen's shape today, and the engine's `Card` header is a
        # different one (a title label plus an actions row).
        header.setStyleSheet(
            f"#settingsCardHeader {{"
            f"background-color: {Palette.BG_CARD_HEADER};"
            f"border-top-left-radius: 8px; border-top-right-radius: 8px;"
            f"border-bottom: 1px solid {Palette.BORDER};"
            f"}}"
        )
        layout = QHBoxLayout(header)
        layout.setContentsMargins(15, 0, 15, 0)
        layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setPixmap(
            get_icon_loader().get_icon("settings", Palette.ACCENT).pixmap(20, 20)
        )
        layout.addWidget(icon_label)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("SAGITTARIUS API KEYS VAULT")
        apply_role(title, StyleRole.HEADING)
        subtitle = QLabel("HMAC SHA256 API Key & Secret Management")
        apply_role(subtitle, StyleRole.CAPTION)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)

        layout.addStretch()

        self._save_button = StyledButton(
            "Save Credentials", role=StyleRole.PRIMARY_BUTTON
        )
        self._save_button.setObjectName("btnSaveCredentials")
        self._save_button.setFixedSize(150, 32)
        self._save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        # PRIMARY_BUTTON carries colour and chrome, not weight. The QSS this
        # replaced set `font-weight: bold`, and dropping it was a visible
        # regression caught in the before/after capture — restored through the
        # widget API so this screen still adds no QSS of its own.
        _save_font = self._save_button.font()
        _save_font.setBold(True)
        self._save_button.setFont(_save_font)
        layout.addWidget(self._save_button)

        return header

    def _build_body(self) -> QWidget:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(14)

        warning = QLabel(
            "Thay đổi được ghi xuống user_config.json ngay khi lưu. "
            "Riêng API Key/Secret cần khởi động lại app để có hiệu lực."
        )
        warning.setObjectName("lblRestartWarning")
        warning.setWordWrap(True)
        warning.setStyleSheet(f"color: {Palette.ACCENT}; font-size: 11px;")
        layout.addWidget(warning)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        row = 0
        row = self._add_field_row(grid, row, "Binance API Key (Public):", "txtApiKey")
        self._api_key_field = self._last_field

        row = self._add_secret_row(grid, row)

        row = self._add_field_row(
            grid, row, "Default Symbols:", "txtDefaultSymbols", "BTCUSDT, ETHUSDT"
        )
        self._default_symbols_field = self._last_field

        row = self._add_field_row(
            grid, row, "Default Interval:", "txtDefaultInterval", "1m"
        )
        self._default_interval_field = self._last_field

        self._add_sync_days_row(grid, row)

        self._status_label = QLabel()
        self._status_label.setObjectName("lblStatus")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._status_label)

        return body

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        apply_role(label, StyleRole.BODY_LABEL)
        return label

    def _make_field(self, object_name: str) -> StyledField:
        """A `StyledField` (engine `FIELD` role) plus the two properties that
        role has no opinion on. Both are set through the widget API rather
        than a second stylesheet, so this screen adds no QSS of its own —
        a stylesheet here would also re-introduce the unscoped cascade
        `BUG-008` fixed."""
        field = StyledField()
        field.setObjectName(object_name)
        field.setMinimumHeight(_FIELD_HEIGHT)
        field.setFont(QFont(_FIELD_FONT_FAMILY))
        return field

    def _add_field_row(
        self,
        grid: QGridLayout,
        row: int,
        label_text: str,
        object_name: str,
        placeholder: str = "",
    ) -> int:
        grid.addWidget(self._field_label(label_text), row, 0)
        field = self._make_field(object_name)
        field.setPlaceholderText(placeholder)
        grid.addWidget(field, row, 1)
        self._last_field = field
        return row + 1

    def _add_secret_row(self, grid: QGridLayout, row: int) -> int:
        grid.addWidget(self._field_label("Binance API Secret (Private):"), row, 0)

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
            f"QPushButton {{ background-color: {_FIELD_BG}; "
            f"border: 1px solid {Palette.BORDER}; border-radius: 6px; }} "
            f"QPushButton:hover {{ background-color: {_FIELD_HOVER_BG}; }}"
        )
        self._reveal_button.toggled.connect(self._toggle_secret_reveal)
        row_layout.addWidget(self._reveal_button)

        grid.addWidget(row_widget, row, 1)
        return row + 1

    def _add_sync_days_row(self, grid: QGridLayout, row: int) -> int:
        grid.addWidget(self._field_label("Default Sync Days:"), row, 0)
        self._sync_days_spin = QSpinBox()
        self._sync_days_spin.setObjectName("spinDefaultSyncDays")
        self._sync_days_spin.setRange(1, 3650)
        self._sync_days_spin.setFixedWidth(130)
        self._sync_days_spin.setStyleSheet(
            f"QSpinBox {{ background-color: {_FIELD_BG}; color: {Palette.TEXT_PRIMARY}; "
            f"border: 1px solid {Palette.BORDER}; border-radius: 6px; min-height: 34px; }}"
        )
        grid.addWidget(self._sync_days_spin, row, 1, Qt.AlignmentFlag.AlignLeft)
        return row + 1
