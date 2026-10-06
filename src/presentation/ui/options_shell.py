"""The workbench shell, with a log line for each Tools → Options page it adds.

`BUG-162` was a second Tools → Options failing on a deleted page widget: the
Engine's closed dialog deleted the widgets it held. The Engine's
`OptionsDialog.done()` now detaches the pages (Engine `BUG-024`, pinned by
`engine.ref`), so this class no longer releases them itself.
"""

from __future__ import annotations

import logging

from sagittarius_engine.extensions.pyside_mvc.workbench.i_options_page import (
    IOptionsPage,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.workbench_shell import (
    WorkbenchShell,
)

#: The window's own logger name, kept from when this lived in `MainWindow`.
logger = logging.getLogger("App.Shell.MainWindow")


class OptionsShell(WorkbenchShell):
    """`WorkbenchShell` that logs each Options page it adds."""

    def add_options_page(self, page: IOptionsPage) -> None:
        """One page of Tools → Options; the log line is what proves, from a
        real process, that the composition root added it."""
        super().add_options_page(page)
        logger.info("[options] Tools > Options page %r added", page.title)
