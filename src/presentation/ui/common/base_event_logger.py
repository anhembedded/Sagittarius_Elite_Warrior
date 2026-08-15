from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QModelIndex
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import (
    DEFAULT_LOG_MAX_ENTRIES,
)

if TYPE_CHECKING:
    from sagittarius_engine.extensions.pyside_mvc.QmlShared.log_list_model import (
        LogListModel,
    )


class BaseEventLogger:
    """
    @brief Reusable tiered event logger bridging application/presenter events to LogListModel.
    @details Supports dev-mode filtering and configurable log entry limit retention.
    """

    def __init__(
        self,
        log_model: LogListModel | None = None,
        is_dev_mode: bool = False,
        emit_signal: Callable[[str, str, bool], None] | None = None,
        max_entries: int = DEFAULT_LOG_MAX_ENTRIES,
    ) -> None:
        self._log_model = log_model
        self._is_dev_mode = is_dev_mode
        self._emit_signal = emit_signal
        self._max_entries = max(1, int(max_entries))

    @property
    def is_dev_mode(self) -> bool:
        return self._is_dev_mode

    @is_dev_mode.setter
    def is_dev_mode(self, value: bool) -> None:
        self._is_dev_mode = bool(value)

    @property
    def max_entries(self) -> int:
        return self._max_entries

    @max_entries.setter
    def max_entries(self, value: int) -> None:
        self._max_entries = max(1, int(value))

    def set_log_model(self, log_model: LogListModel) -> None:
        self._log_model = log_model

    def log(self, message: str, level: str = "info", is_dev: bool = False) -> None:
        """Appends a log message if conditions are met."""
        if is_dev and not self._is_dev_mode:
            return

        if self._emit_signal is not None:
            self._emit_signal(message, level, is_dev)
        elif self._log_model is not None:
            self._log_model.append(message, level=level)
            self._trim_model_entries(self._log_model)

    def _trim_model_entries(self, model: LogListModel) -> None:
        count = model.rowCount()
        if not isinstance(count, int) or isinstance(count, bool):
            return

        while count > self._max_entries:
            model.beginRemoveRows(QModelIndex(), 0, 0)
            if hasattr(model, "_entries") and model._entries:
                model._entries.pop(0)
            model.endRemoveRows()
            count = model.rowCount()
            if not isinstance(count, int) or isinstance(count, bool):
                break

    def info(self, message: str, is_dev: bool = False) -> None:
        self.log(message, level="info", is_dev=is_dev)

    def success(self, message: str, is_dev: bool = False) -> None:
        self.log(message, level="success", is_dev=is_dev)

    def warning(self, message: str, is_dev: bool = False) -> None:
        self.log(message, level="warning", is_dev=is_dev)

    def error(self, message: str, is_dev: bool = False) -> None:
        self.log(message, level="error", is_dev=is_dev)

    def dev_trace(self, action: str, **fields: Any) -> None:
        if not self._is_dev_mode:
            return
        suffix = " ".join(f"{k}={v!r}" for k, v in fields.items())
        msg = f"[DEV] {action} {suffix}".rstrip()
        self.log(msg, level="info", is_dev=True)
