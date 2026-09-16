"""
@brief `ConfirmOverlay` — an `Overlay` asking one yes/no question.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..controls import StyledButton
from ..overlay import Overlay
from ..style import StyleRole

#: Fallback labels. English, and deliberately not a localisation mechanism:
#: this package knows no consuming application, so it cannot know the app's
#: language. Every real consumer passes its own strings (the app this was
#: written for passes Vietnamese); these exist so a throwaway confirm in a
#: test or an example is not forced to invent wording.
_DEFAULT_CONFIRM_TEXT = "Confirm"
_DEFAULT_CANCEL_TEXT = "Cancel"


class ConfirmOverlay(Overlay):
    """
    @brief An `Overlay` with a wrapped message body and a Cancel/Confirm
    footer, where the confirm button carries either the primary or the
    danger role.

    @details
    `confirm_button` and `cancel_button` are public: a consumer disabling
    Confirm until input validates is the whole reason to reach for them.

    **Do not re-annotate either attribute in a subclass `__init__` body.**
    `_build_buttons()` runs from `Overlay.__init__`, so both buttons already
    exist by the time a subclass's own body starts; a line like
    `self.confirm_button: StyledButton | None = None` written afterwards
    overwrites the real button with `None`, and any `if ... is not None`
    guard around it silently stops running. That is not hypothetical — it is
    live today in the consuming app's `CapitalDialogWidget`, whose Apply
    button can never be disabled on invalid input for exactly this reason.

    Confirm calls `accept()`, Cancel calls `reject()`, so `exec()` and
    `QDialog.accepted`/`rejected` both report the answer. The app's two
    pre-existing confirm dialogs instead take an `on_confirm` callback and
    call `close()` — which makes `exec()` return `Rejected` even when the
    user confirmed. Migrating them onto this class means rewiring those call
    sites; that is the migration task's work, not a shape this base copies.
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        *,
        message: str = "",
        confirm_text: str = _DEFAULT_CONFIRM_TEXT,
        cancel_text: str = _DEFAULT_CANCEL_TEXT,
        danger: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        # Set before `super().__init__()`, not after: `Overlay.__init__`
        # calls `_build_buttons()`, which reads all three. Verified
        # empirically on PySide6 6.11.2 that a plain Python attribute
        # assigned before the Qt base is constructed both succeeds and
        # survives that construction — the same "check it against the real
        # Qt, do not reason about it" discipline `Surface`'s abstractness
        # and `DateTimeField`'s base class were each settled by.
        self._danger = danger
        self._confirm_text = confirm_text
        self._cancel_text = cancel_text

        super().__init__(title, subtitle, parent=parent)

        self._message_label = QLabel(message)
        self._message_label.setWordWrap(True)
        self._message_label.setVisible(bool(message))
        self.body_layout.addWidget(self._message_label)

    @property
    def message(self) -> str:
        return self._message_label.text()

    @message.setter
    def message(self, value: str) -> None:
        self._message_label.setText(value)
        self._message_label.setVisible(bool(value))

    @property
    def danger(self) -> bool:
        """Whether Confirm is rendered as the destructive choice. Read-only
        after construction: `StyledButton` resolves its QSS from the role it
        was built with, so flipping this would mean rebuilding the button,
        and no consumer has ever needed a confirm dialog to change severity
        while open."""
        return self._danger

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        # Leading stretch: every multi-button dialog in the consuming app
        # right-aligns its footer, with confirm rightmost and cancel to its
        # left. Matching that here means a migrated dialog does not shift.
        row.addStretch(1)
        self.cancel_button = StyledButton(
            self._cancel_text, role=StyleRole.SECONDARY_BUTTON
        )
        self.cancel_button.clicked.connect(self.reject)
        row.addWidget(self.cancel_button)
        self.confirm_button = StyledButton(
            self._confirm_text,
            role=(
                StyleRole.DANGER_BUTTON if self._danger else StyleRole.PRIMARY_BUTTON
            ),
        )
        self.confirm_button.clicked.connect(self.accept)
        row.addWidget(self.confirm_button)
        return row
