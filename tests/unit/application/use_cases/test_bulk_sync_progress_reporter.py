from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.bulk_sync_market_data.progress_reporter import (
    BulkSyncProgressReporter,
)


def test_bulk_sync_progress_reporter_empty():
    mock_publisher = Mock()
    reporter = BulkSyncProgressReporter(mock_publisher, total_targets=0)
    reporter.report_empty()

    assert mock_publisher.publish.call_count == 1
    event = mock_publisher.publish.call_args[0][0]
    assert isinstance(event, BulkSyncProgressEvent)
    assert event.is_complete is True
    assert event.total_targets == 0
    assert event.message == "No targets to sync."


def test_bulk_sync_progress_reporter_target_and_completion():
    mock_publisher = Mock()
    reporter = BulkSyncProgressReporter(mock_publisher, total_targets=2)

    reporter.report_target("BTCUSDT", "1m")
    assert reporter.completed_count == 1
    assert mock_publisher.publish.call_count == 1
    ev1 = mock_publisher.publish.call_args[0][0]
    assert ev1.current_index == 1
    assert ev1.symbol == "BTCUSDT"
    assert ev1.has_error is False
    assert "[1/2] BTCUSDT (1m) complete." in ev1.message

    reporter.report_target("ETHUSDT", "5m", has_error=True, error_msg="Timeout")
    assert reporter.completed_count == 2
    assert mock_publisher.publish.call_count == 2
    ev2 = mock_publisher.publish.call_args[0][0]
    assert ev2.current_index == 2
    assert ev2.has_error is True
    assert ev2.message == "Failed: Timeout"

    reporter.report_completed()
    assert mock_publisher.publish.call_count == 3
    ev3 = mock_publisher.publish.call_args[0][0]
    assert ev3.is_complete is True
    assert ev3.current_index == 2
    assert ev3.message == "Bulk sync completed successfully."
