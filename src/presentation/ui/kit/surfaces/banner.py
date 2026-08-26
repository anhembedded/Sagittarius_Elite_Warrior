"""
@brief `Banner` — a `Panel` carrying one short severity-coloured message.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..controls import StyledButton
from ..style import StyleRole, apply_role, banner_accent
from ..surface import Panel


class Severity:
    """
    @brief The three banner severities, as the `StyleRole` each maps to.

    @details A namespace over the roles rather than a second enum wrapping
    them: `apply_role()` already takes a `StyleRole`, and a `Severity.WARN`
    that had to be translated into `StyleRole.BANNER_WARN` at every call
    would be a parallel vocabulary with nothing extra to say.
    """

    INFO = StyleRole.BANNER_INFO
    WARN = StyleRole.BANNER_WARN
    DANGER = StyleRole.BANNER_DANGER
    #: The pass half of a check that can also fail. This class was written
    #: claiming to cover an audit banner that "switches success/danger at
    #: runtime" and then shipped without a success to switch to.
    SUCCESS = StyleRole.BANNER_SUCCESS


_SEVERITIES = frozenset(
    {Severity.INFO, Severity.WARN, Severity.DANGER, Severity.SUCCESS}
)


class Banner(Panel):
    """
    @brief A `Panel` with an optional leading icon, a message, and an
    optional trailing action button, coloured by severity.

    @details
    Covers four of the reference consumer's five banners: its preview
    (info + icon + static text), stale (warning + icon + dynamic text +
    a "run again" button), coverage (warning + text only) and audit
    (success/danger switched at runtime + emoji icon + text).

    **Severity is settable after construction**, unlike the consumer's four
    backtest banners which each bake their colours in at build time. The
    audit banner is why: it recolours itself on every sync depending on
    whether the check passed. Making that the general case costs nothing —
    the four static ones simply never call `set_severity` again.

    **Its fifth banner is deliberately not covered.** That one's whole body
    is a progress bar with a cancel button whose label changes between
    "cancel" and "cancelling"; it has no icon slot and no message of its
    own. It shares only "a rounded panel that stays hidden until needed"
    with these four, so folding it in would mean a `progress: bool` that
    switches the class between two unrelated layouts. Recorded in
    `EPIC-007B` as a separate `ProgressBanner` candidate.

    The icon is a `str`, not a pixmap: the consumer's banners are split
    between icon-loader pixmaps and bare emoji, and this package has no
    icon loader to depend on. A consumer wanting a pixmap sets one on
    `icon_label` directly.

    Not dismissable. None of the five has a close button — visibility is
    always driven externally from view-model state, so a `dismissable`
    flag would be a parameter with no caller.
    """

    def __init__(
        self,
        message: str = "",
        *,
        severity: StyleRole = Severity.INFO,
        icon: str = "",
        action_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if severity not in _SEVERITIES:
            raise ValueError(
                f"Banner severity must be one of "
                f"Severity.INFO/WARN/DANGER/SUCCESS, "
                f"got {severity}"
            )
        self._severity = severity

        row = QHBoxLayout()

        self.icon_label = QLabel(icon)
        self.icon_label.setVisible(bool(icon))
        row.addWidget(self.icon_label)

        self._message_label = QLabel(message)
        self._message_label.setWordWrap(True)
        row.addWidget(self._message_label, 1)

        self.action_button = StyledButton(action_text, role=StyleRole.SECONDARY_BUTTON)
        self.action_button.setVisible(bool(action_text))
        row.addWidget(self.action_button)

        self.body_layout.addLayout(row)
        apply_role(self, severity)
        self._sync_text_colour()

    @property
    def severity(self) -> StyleRole:
        return self._severity

    @property
    def message(self) -> str:
        return self._message_label.text()

    @message.setter
    def message(self, value: str) -> None:
        self._message_label.setText(value)

    @property
    def icon(self) -> str:
        return self.icon_label.text()

    @icon.setter
    def icon(self, value: str) -> None:
        self.icon_label.setText(value)
        self.icon_label.setVisible(bool(value))

    def set_severity(self, severity: StyleRole) -> None:
        """@brief Recolours the banner. The one thing the consumer's audit
        banner needs that its four backtest banners do not."""
        if severity not in _SEVERITIES:
            raise ValueError(
                f"Banner severity must be one of "
                f"Severity.INFO/WARN/DANGER/SUCCESS, "
                f"got {severity}"
            )
        self._severity = severity
        apply_role(self, severity)
        self._sync_text_colour()

    def _sync_text_colour(self) -> None:
        """The severity's QSS is scoped to the panel, so it never reaches
        the text inside it.

        This class shipped without this, and the message rendered at the
        widget's default colour — dark grey on a dark banner, effectively
        invisible. All four real banners set the severity colour on their
        text explicitly, and bold on three of the four; the fourth, a
        coverage warning, gains bold here, which is the recorded difference.
        """
        colour = banner_accent(self._severity)
        rule = f"background-color: transparent; color: {colour}; font-weight: bold;"
        self.icon_label.setStyleSheet(f"QLabel {{ {rule} }}")
        self._message_label.setStyleSheet(f"QLabel {{ {rule} }}")

    def set_action_text(self, text: str) -> None:
        """@brief Sets the trailing button's label, hiding it when empty.
        Settable rather than construction-only because the consumer's
        cancel action relabels itself mid-flight."""
        self.action_button.setText(text)
        self.action_button.setVisible(bool(text))
