"""The Welcome surface: what this application is, and one way in (ADR D13).

The first screen a user sees, and the first surface **the shell itself owns** —
every other one is a bounded context's or a legacy screen the shell is still
carrying. It is a `WorkbenchSurface` like the others, with two places filled:
`HEADER` carries the environment banner the host puts there itself, and
`WORKSPACE` says what the app is and offers **Start**.

@par Why it is this small
The user's decision of 2026-09-13 (ADR D13): the app opens on a screen about
the application, not on a developer testbed that happens to be first in the
sidebar. What a Welcome screen must do is name the app, say which venue this
run talks to, and get out of the way. Everything else it *could* show is
something a surface already shows better.

@par Start is an intent
The button emits `start_requested`, and this view neither knows nor decides
where that goes (`start_requested_event.py` says why). A real login can replace
the button without touching anything else.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

_START_TEXT = "Start"
_DEV_MODE_TEXT = "Developer mode"
_RESTART_NOTICE = "Developer mode takes effect after a restart."
_RESTART_TEXT = "Restart now"


class WelcomeView(BaseView):
    """@brief The Welcome surface's widgets, and the one signal it raises."""

    #: The developer-mode switch changed. The Presenter writes it; this view
    #: does not touch configuration.
    dev_mode_toggled = Signal(bool)

    #: The user asked for the restart the switch needs to take effect.
    restart_requested = Signal()

    #: The user pressed Start. The Presenter turns it into an intent on the
    #: bus; nothing here decides what Start means.
    #:
    #: `snake_case`, unlike every camelCase signal in `presentation/ui/**`:
    #: that tree carries a per-file `N815` ignore for Qt's own convention and
    #: `shell/` does not, so the choice here is between renaming the signal and
    #: widening a lint exemption nobody asked for. Qt is indifferent; the linter
    #: is not.
    start_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._surface = WorkbenchSurface(surfaces_by_id()["welcome"])

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._surface)

        self._title = QLabel()
        self._title.setObjectName("lblWelcomeTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # The app's own name, larger than body text, and the one place this
        # screen leans on a font weight rather than a stylesheet: a title that
        # reads as a title is the platform's own `QFont`, not a colour.
        title_font = self._title.font()
        title_font.setPointSize(title_font.pointSize() + 8)
        title_font.setBold(True)
        self._title.setFont(title_font)

        self._subtitle = QLabel()
        self._subtitle.setObjectName("lblWelcomeSubtitle")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle.setWordWrap(True)

        self._start_button = QPushButton(_START_TEXT)
        self._start_button.setObjectName("btnStart")
        self._start_button.setDefault(True)
        self._start_button.clicked.connect(self.start_requested)

        workspace = QWidget()
        column = QVBoxLayout(workspace)
        column.addStretch(1)
        column.addWidget(self._title)
        column.addWidget(self._subtitle)
        column.addSpacing(16)
        column.addWidget(self._start_button, 0, Qt.AlignmentFlag.AlignCenter)
        column.addStretch(2)
        self._surface.place_widget(Place.WORKSPACE, workspace)
        self._place_developer_mode_switch()

    def _place_developer_mode_switch(self) -> None:
        """The switch, its notice and the restart button, in the header.

        In `HEADER` rather than the workspace because that is where HLD §4.6
        puts it, and because it is not what the screen is *for*: the workspace
        answers "what is this and how do I start", and a setting that needs a
        restart belongs beside the window's own controls.
        """
        self._dev_mode_switch = QCheckBox(_DEV_MODE_TEXT)
        self._dev_mode_switch.setObjectName("chkDeveloperMode")
        self._dev_mode_switch.setToolTip(
            "Shows the Dev Board's probes and the chart diagnostics. "
            "Read once at boot, so changing it needs a restart."
        )
        self._dev_mode_switch.toggled.connect(self.dev_mode_toggled)

        self._restart_notice = QLabel(_RESTART_NOTICE)
        self._restart_notice.setObjectName("lblRestartNotice")
        self._restart_notice.setVisible(False)

        self._restart_button = QPushButton(_RESTART_TEXT)
        self._restart_button.setObjectName("btnRestartNow")
        self._restart_button.setVisible(False)
        self._restart_button.clicked.connect(self.restart_requested)

        self._surface.place_widget(Place.HEADER, self._dev_mode_switch)
        self._surface.place_widget(Place.HEADER, self._restart_notice)
        self._surface.place_widget(Place.HEADER, self._restart_button)

    def show_developer_mode(self, *, enabled: bool) -> None:
        """Sets the switch to what configuration says, without reporting it
        back as a change the user made.

        `blockSignals` and not a flag: `setChecked()` emits `toggled`, and a
        Presenter that wrote the value it had just read would save the file on
        every boot — and would turn "the app started" into "the user changed a
        setting".
        """
        self._dev_mode_switch.blockSignals(True)
        self._dev_mode_switch.setChecked(enabled)
        self._dev_mode_switch.blockSignals(False)

    def show_restart_is_needed(self) -> None:
        """Says what the switch did and offers the only thing that applies it.

        Shown after the write, never before: the notice is a fact about
        configuration on disk, not a promise about one.
        """
        self._restart_notice.setVisible(True)
        self._restart_button.setVisible(True)

    def show_application(self, name: str, version: str) -> None:
        """Names the app and its version — the Presenter reads both from
        configuration, because the shell cannot reach the legacy window
        title and a checkout has no package metadata to ask."""
        self._title.setText(name)
        self._subtitle.setText(f"Version {version}")

    def show_venue(self, description: str) -> None:
        """Appends what this run talks to. A user who does not know whether
        they are on Testnet is a user one click from a real order."""
        self._subtitle.setText(f"{self._subtitle.text()} · {description}")

    @property
    def surface(self) -> WorkbenchSurface:
        """For a test or a preview that needs the host itself."""
        return self._surface
