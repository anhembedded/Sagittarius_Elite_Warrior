from __future__ import annotations

import logging

from PySide6.QtCore import Signal


class SignalLogHandler(logging.Handler):
    """
    @brief Bridges standard Python logging to a Qt Signal for UI display.

    @details
    Handlers attached to the app-wide "App" logger outlive the screen that
    installed them, so once that screen's C++ object is deleted the bound
    signal raises RuntimeError — and because every `App.*` logger propagates
    here, a single dead screen would break logging for the WHOLE app
    (originally surfaced as unrelated icon-loading tests failing, since
    IconLoader logs a warning through `App.IconLoader`).

    Detaching on the first such failure keeps that blast radius at zero.
    """

    def __init__(self, signal: Signal, logger_name: str = "App") -> None:
        super().__init__()
        self.signal = signal
        self._logger_name = logger_name
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.signal.emit(self.format(record))
        except RuntimeError:
            self.detach()

    def detach(self) -> None:
        """Removes this handler from its logger. Safe to call twice."""
        logging.getLogger(self._logger_name).removeHandler(self)
