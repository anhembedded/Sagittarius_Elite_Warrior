from __future__ import annotations

from unittest.mock import MagicMock

from Sagittarius_Elite_Warrior.src.presentation.ui.common.base_event_logger import (
    BaseEventLogger,
)


def test_base_event_logger_appends_to_log_model() -> None:
    mock_log_model = MagicMock()
    logger = BaseEventLogger(log_model=mock_log_model, is_dev_mode=False)

    logger.info("Hello info")
    mock_log_model.append.assert_called_once_with("Hello info", level="info")

    mock_log_model.reset_mock()
    logger.success("Operation success")
    mock_log_model.append.assert_called_once_with("Operation success", level="success")

    mock_log_model.reset_mock()
    logger.warning("Warning message")
    mock_log_model.append.assert_called_once_with("Warning message", level="warning")

    mock_log_model.reset_mock()
    logger.error("Error occurred")
    mock_log_model.append.assert_called_once_with("Error occurred", level="error")


def test_base_event_logger_dev_mode_filtering() -> None:
    mock_log_model = MagicMock()
    logger = BaseEventLogger(log_model=mock_log_model, is_dev_mode=False)

    # In non-dev mode, dev logs must be suppressed
    logger.dev_trace("calculate_math", duration_ms=15)
    mock_log_model.append.assert_not_called()

    logger.log("Internal debug step", level="info", is_dev=True)
    mock_log_model.append.assert_not_called()

    # Enable dev mode
    logger.is_dev_mode = True
    logger.dev_trace("calculate_math", duration_ms=15)
    mock_log_model.append.assert_called_once_with(
        "[DEV] calculate_math duration_ms=15", level="info"
    )


def test_base_event_logger_with_emit_signal() -> None:
    mock_signal_emitter = MagicMock()
    logger = BaseEventLogger(emit_signal=mock_signal_emitter, is_dev_mode=False)

    logger.info("Test message")
    mock_signal_emitter.assert_called_once_with("Test message", "info", False)

    mock_signal_emitter.reset_mock()
    logger.is_dev_mode = True
    logger.dev_trace("trace_action", count=5)
    mock_signal_emitter.assert_called_once_with(
        "[DEV] trace_action count=5", "info", True
    )
