"""
@brief Unit tests for UIWatchdog freeze and deadlock detector from sagittarius_engine.
"""

from __future__ import annotations

import logging
import time
from unittest.mock import MagicMock

from sagittarius_engine.extensions.pyside_mvc import (
    UIWatchdog,
    setup_qt_signal_handling,
)


def test_watchdog_starts_and_stops_cleanly(qapp) -> None:
    """Watchdog can be started and stopped without hanging or leaking threads."""
    logger = logging.getLogger("TestWatchdog")
    watchdog = UIWatchdog(
        freeze_threshold_sec=0.5,
        check_interval_sec=0.1,
        heartbeat_interval_ms=50,
        logger=logger,
    )

    watchdog.start()
    assert watchdog._is_running is True
    assert watchdog._monitor_thread is not None
    assert watchdog._monitor_thread.is_alive()

    # Record some heartbeats
    watchdog.record_heartbeat()
    time.sleep(0.15)
    assert watchdog._is_frozen is False

    watchdog.stop()
    assert watchdog._is_running is False
    assert watchdog._monitor_thread is None


def test_watchdog_detects_freeze_and_invokes_callback(qapp) -> None:
    """When heartbeat stops for longer than threshold, watchdog detects freeze and triggers callback."""
    mock_callback = MagicMock()
    logger = logging.getLogger("TestWatchdogFreeze")

    watchdog = UIWatchdog(
        freeze_threshold_sec=0.2,
        check_interval_sec=0.05,
        heartbeat_interval_ms=20,
        logger=logger,
        on_freeze_callback=mock_callback,
    )

    watchdog.start()
    # Stop sending heartbeats and sleep past threshold
    time.sleep(0.35)

    assert watchdog._is_frozen is True
    mock_callback.assert_called_once()
    freeze_msg = mock_callback.call_args[0][0]
    assert "UI FREEZE DETECTED" in freeze_msg

    # Test recovery when heartbeat resumes
    watchdog.record_heartbeat()
    assert watchdog._is_frozen is False

    watchdog.stop()


def test_setup_qt_signal_handling(qapp) -> None:
    """Signal handling sets up a running QTimer without errors."""
    timer = setup_qt_signal_handling(qapp)
    assert timer.isActive() is True
    timer.stop()
