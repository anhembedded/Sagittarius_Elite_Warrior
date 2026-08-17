from unittest.mock import Mock

from PySide6.QtWidgets import QPushButton, QTableWidget, QVBoxLayout, QWidget

from sagittarius_engine.extensions.pyside_mvc import BaseView


def test_enable_dev_click_logging_logs_existing_button(qapp):
    # Arrange
    view = BaseView()
    view.monitor_card = Mock()
    layout = QVBoxLayout(view)
    button = QPushButton("Load History")
    layout.addWidget(button)

    # Act
    view.enable_dev_click_logging()
    button.click()

    # Assert
    view.monitor_card.append_log.assert_called_once_with('User clicked "Load History"')


def test_enable_dev_click_logging_covers_button_added_after_watching_starts(qapp):
    """
    A button added directly to the View AFTER enable_dev_click_logging() was
    called must still be logged automatically — no per-button/per-screen
    wiring needed for new buttons.
    """
    # Arrange
    view = BaseView()
    view.monitor_card = Mock()
    layout = QVBoxLayout(view)
    view.enable_dev_click_logging()

    # Act — button created after watching started
    new_button = QPushButton("Sync")
    layout.addWidget(new_button)
    new_button.click()

    # Assert
    view.monitor_card.append_log.assert_called_once_with('User clicked "Sync"')


def test_enable_dev_click_logging_covers_button_in_new_nested_container(qapp):
    """
    A whole new sub-widget (with its own button) added later must also be
    covered, not just buttons added as direct children of the View.
    """
    # Arrange
    view = BaseView()
    view.monitor_card = Mock()
    layout = QVBoxLayout(view)
    view.enable_dev_click_logging()

    # Act — a new subtree containing a button, added after watching started
    sub_container = QWidget()
    sub_layout = QVBoxLayout(sub_container)
    nested_button = QPushButton("Clear Local Data")
    sub_layout.addWidget(nested_button)
    layout.addWidget(sub_container)
    nested_button.click()

    # Assert
    view.monitor_card.append_log.assert_called_once_with(
        'User clicked "Clear Local Data"'
    )


def test_enable_dev_click_logging_covers_table_cell_widget_button(qapp):
    """
    Mirrors DatabaseStatusCard's real per-row "Sync" button pattern: a button
    added via QTableWidget.setCellWidget() after watching started.
    """
    # Arrange
    view = BaseView()
    view.monitor_card = Mock()
    layout = QVBoxLayout(view)
    table = QTableWidget(0, 1)
    layout.addWidget(table)
    view.enable_dev_click_logging()

    # Act — row/cell widget added after watching started
    table.insertRow(0)
    row_button = QPushButton("Sync")
    table.setCellWidget(0, 0, row_button)
    row_button.click()

    # Assert
    view.monitor_card.append_log.assert_called_once_with('User clicked "Sync"')


def test_log_dev_action_is_noop_without_monitor_card(qapp):
    """
    A View with no `monitor_card` attribute must not crash — the default
    log_dev_action() is a safe no-op, only overriding views opt into a sink.
    """
    # Arrange
    view = BaseView()
    layout = QVBoxLayout(view)
    button = QPushButton("Start")
    layout.addWidget(button)
    view.enable_dev_click_logging()

    # Act / Assert — must not raise
    button.click()
