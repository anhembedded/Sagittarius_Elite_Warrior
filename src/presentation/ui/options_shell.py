"""The workbench shell whose Tools → Options can be opened more than once.

The Engine's `WorkbenchShell.show_options()` deletes the dialog on close, and a
dialog deletes the widgets it holds. Each page builds its widget once and the
shell keeps the page, so the second Tools → Options added a deleted widget
(`libshiboken: ... already deleted`, `BUG-162`). `finished` fires before the
deletion is queued: the widgets are orphaned there and outlive the dialog.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from sagittarius_engine.extensions.pyside_mvc.workbench.i_options_page import (
    IOptionsPage,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.options_dialog import (
    OptionsDialog,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.workbench_shell import (
    WorkbenchShell,
)

#: The window's own logger name, kept from when this lived in `MainWindow`.
logger = logging.getLogger("App.Shell.MainWindow")


class OptionsShell(WorkbenchShell):
    """`WorkbenchShell` whose Options pages survive the dialog."""

    def add_options_page(self, page: IOptionsPage) -> None:
        """One page of Tools → Options; the log line is what proves, from a
        real process, that the composition root added it."""
        super().add_options_page(page)
        logger.info("[options] Tools > Options page %r added", page.title)

    def show_options(self) -> OptionsDialog:
        dialog = OptionsDialog(self._options_pages, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.finished.connect(self._release_options_widgets)
        dialog.exec()
        return dialog

    def _release_options_widgets(self) -> None:
        for page in self._options_pages:
            page.widget().setParent(None)
        logger.debug(
            "[options] Tools > Options closed; %d page widget(s) kept for the next open",
            len(self._options_pages),
        )
