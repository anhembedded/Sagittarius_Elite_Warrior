from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sagittarius_engine.extensions.pyside_mvc.QmlShared.log_list_model import (
        LogListModel,
    )


class BaseEventLogger:
    """
    @brief Reusable tiered event logger bridging application/presenter events to LogListModel.
    @details Supports dev-mode filtering so verbose/technical trace logs only appear
    when running with --dev (ConfigKeys.DEV_MODE / DEV_MODE_CONFIG_KEY).
    """

    def __init__(
        self,
        log_model: LogListModel | None = None,
        is_dev_mode: bool = False,
        emit_signal: Callable[[str, str, bool], None] | None = None,
    ) -> None:
        self._log_model = log_model
        self._is_dev_mode = is_dev_mode
        self._emit_signal = emit_signal

    @property
    def is_dev_mode(self) -> bool:
        return self._is_dev_mode

    @is_dev_mode.setter
    def is_dev_mode(self, value: bool) -> None:
        self._is_dev_mode = bool(value)

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
