"""Tools → Options → Developer (`EPIC-033C`).

The developer-mode switch lived on the Welcome screen (ADR D14) until the
workbench window dropped Welcome: the app opens on the last mode, and a
setting belongs in Options (MS `win-dialog-box`, HLD §11.2). The behaviour is
the same one, now under the dialog's commit buttons: the page writes
`dev.mode` only on OK or Apply, never on the click itself, and a written value
that differs from this run's offers a restart, the only thing that applies it
(`restart.py` says why).

An `IOptionsPage` (the Engine's, satisfied structurally). Nothing here takes
long enough to need a coordinator: reading one key or writing one.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Sequence

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import (
    IConfigReader,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_writer import IConfigWriter
from Sagittarius_Elite_Warrior.src.shell.developer_options.restart import restart_now

logger = logging.getLogger("App.Shell.DeveloperOptions")

_TITLE = "Developer"
_SWITCH_TEXT = "&Developer mode"
_RESTART_NOTICE = "Developer mode takes effect after a restart."
_RESTART_TEXT = "&Restart now"


def _start_detached(arguments: Sequence[str]) -> bool:
    """Qt's own launcher, its `(started, pid)` answer narrowed to "did it
    start": a tuple returned as a `bool` is truthy forever."""
    started, _pid = QProcess.startDetached(arguments[0], list(arguments[1:]))
    return bool(started)


class DeveloperOptionsPage:
    """The developer-mode switch, applied with the dialog's OK or Apply."""

    def __init__(
        self,
        config: IConfigReader,
        writer: IConfigWriter,
        *,
        running_with_dev_mode: bool,
    ) -> None:
        self._config = config
        self._writer = writer
        self._running_with_dev_mode = running_with_dev_mode
        self._listener: Callable[[], None] | None = None
        self._widget = QWidget()
        self._widget.setObjectName("options::developer")
        self._switch = QCheckBox(_SWITCH_TEXT)
        self._switch.setObjectName("options::developer::mode")
        self._switch.toggled.connect(self._on_edited)
        self._notice = QLabel(_RESTART_NOTICE)
        self._restart = QPushButton(_RESTART_TEXT)
        self._restart.setObjectName("options::developer::restart")
        self._restart.clicked.connect(self._on_restart)
        layout = QFormLayout(self._widget)
        layout.addRow(self._switch)
        layout.addRow(self._notice)
        layout.addRow(self._restart)
        self.revert()

    # -- IOptionsPage ----------------------------------------------------------

    @property
    def title(self) -> str:
        return _TITLE

    def widget(self) -> QWidget:
        return self._widget

    def apply(self) -> None:
        enabled = self._switch.isChecked()
        previous = self._saved()
        try:
            self._writer.set(ConfigKeys.DEV_MODE.value, enabled)
            self._writer.save()
        except (OSError, ValueError):
            # `set()` already changed the value in memory; put it back, then
            # the switch: a page showing the unsaved value, or offering a
            # restart for it, would be a lie the user acts on.
            self._writer.set(ConfigKeys.DEV_MODE.value, previous)
            logger.exception(
                "Developer mode = %s was not saved; the setting is unchanged",
                enabled,
            )
            self.revert()
            return
        logger.info("Developer mode written as %s", enabled)
        self._show_restart_state()

    def revert(self) -> None:
        self._switch.blockSignals(True)
        self._switch.setChecked(self._saved())
        self._switch.blockSignals(False)
        self._show_restart_state()

    def is_dirty(self) -> bool:
        return self._switch.isChecked() != self._saved()

    def validation_message(self) -> str | None:
        return None

    def set_change_listener(self, listener: Callable[[], None]) -> None:
        self._listener = listener

    # -- the restart -----------------------------------------------------------

    def _saved(self) -> bool:
        return bool(self._config.get(ConfigKeys.DEV_MODE.value, False))

    def _show_restart_state(self) -> None:
        """The notice and the restart button only while the saved value
        differs from the one this run started with."""
        needed = self._saved() != self._running_with_dev_mode
        self._notice.setVisible(needed)
        self._restart.setVisible(needed)

    def _on_edited(self, checked: bool) -> None:
        if self._listener is not None:
            self._listener()

    def _on_restart(self) -> None:
        restart_now(
            [sys.executable, *sys.argv],
            dev_mode_enabled=self._saved(),
            start_detached=_start_detached,
            quit_application=QApplication.quit,
        )
