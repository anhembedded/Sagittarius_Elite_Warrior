"""Thin render and interaction tests for `DatabaseStatusTable.qml`.

Loads the file directly into a bare `QQuickWidget` with hand-set `vm`/
`Theme` context properties, sidestepping `QmlOverlay` (see NOTES.md — that
pulls in `sagittarius_engine`, a separate repo not always present in a dev
environment). A real host still goes through `QmlOverlay`-style hosting
normally; this file only proves the `.qml` loads and its bindings point at
properties the VM/model actually have.
"""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, Qt, QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtTest import QTest

from .test_database_status_vm import _seeded_model

_QML = Path(__file__).resolve().parents[1] / "DatabaseStatusTable.qml"


class _FakeTheme(QObject):
    """Minimal token set these `.qml` files read — a local double, not
    another widget's theme class, so this widget's tests do not depend on
    another widget's directory (conftest.py's rule)."""

    @Property(str, constant=True)
    def textPrimary(self) -> str:
        return "#eeeeee"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def muted(self) -> str:
        return "#999999"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def accent(self) -> str:
        return "#ff9900"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def border(self) -> str:
        return "#333333"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def success(self) -> str:
        return "#33cc66"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def danger(self) -> str:
        return "#cc3333"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def stateIdleBg(self) -> str:
        return "#1a1a1a"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def stateActiveTint(self) -> str:
        return "#33ff9926"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def stateNavBorder(self) -> str:
        return "#444444"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def bg(self) -> str:
        return "#0c0c0e"  # token-exempt: fake theme double, not a real Palette value


def _load(qapp, vm):
    from Sagittarius_Elite_Warrior.src.presentation.ui.qml.DatabaseStatusTable.database_status_vm import (
        DatabaseStatusVM,
    )

    assert isinstance(vm, DatabaseStatusVM)
    theme = _FakeTheme()
    quick = QQuickWidget()
    quick._database_status_vm = vm
    quick._database_status_theme = theme
    quick.rootContext().setContextProperty("vm", vm)
    quick.rootContext().setContextProperty("Theme", theme)
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.setSource(QUrl.fromLocalFile(str(_QML)))
    assert quick.status() is QQuickWidget.Status.Ready, quick.errors()
    quick.resize(900, 260)
    quick.show()
    qapp.processEvents()
    return quick, quick.rootObject()


def _vm_with_two_rows(unhealthy: bool = False):
    from Sagittarius_Elite_Warrior.src.presentation.ui.qml.DatabaseStatusTable.database_status_vm import (
        DatabaseStatusVM,
    )

    model = _seeded_model()  # BTCUSDT/1s, healthy
    model.upsert_row(
        symbol="BTCUSDT",
        first_record="2026-07-27 07:30:00",
        last_record="2026-08-26 07:00:00",
        total_candles="1,440",
        status_text="Missing 3 gaps" if unhealthy else "OK",
        interval="30m",
    )
    return DatabaseStatusVM(model), model


def test_component_loads_and_renders_one_row_per_shard(qapp, qml_item):
    vm, _model = _vm_with_two_rows()
    quick, root = _load(qapp, vm)

    assert root.objectName() == "databaseStatusBody"
    assert qml_item(root, "databaseStatusSymbol_BTCUSDT_1s") is not None
    assert qml_item(root, "databaseStatusSymbol_BTCUSDT_30m") is not None
    quick.close()
    quick.deleteLater()


def test_row_count_badge_matches_the_model(qapp, qml_item):
    vm, _model = _vm_with_two_rows()
    quick, root = _load(qapp, vm)

    badge = qml_item(root, "panelHeaderBadgeText")
    assert badge.property("text") == "2 shards"
    quick.close()
    quick.deleteLater()


def test_gaps_action_only_shows_on_an_unhealthy_row(qapp, qml_item):
    vm, _model = _vm_with_two_rows(unhealthy=True)
    quick, root = _load(qapp, vm)

    assert (
        qml_item(root, "btnDatabaseStatusGaps_BTCUSDT_1s").property("visible") is False
    )
    assert (
        qml_item(root, "btnDatabaseStatusGaps_BTCUSDT_30m").property("visible") is True
    )
    quick.close()
    quick.deleteLater()


def test_clicking_sync_requests_the_action_for_the_right_row(qapp, qml_item):
    vm, _model = _vm_with_two_rows()
    quick, root = _load(qapp, vm)
    requests: list[tuple[str, str, str]] = []
    vm.rowActionRequested.connect(lambda a, s, i: requests.append((a, s, i)))

    button = qml_item(root, "btnDatabaseStatusSync_BTCUSDT_30m")
    point = button.mapToScene(button.boundingRect().center())
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=point.toPoint())
    qapp.processEvents()

    assert requests == [("sync", "BTCUSDT", "30m")]
    quick.close()
    quick.deleteLater()


def test_typing_in_the_search_field_reaches_the_vm_and_filters_rows(qapp, qml_item):
    """Real keystrokes, not a hand-invoked `textEdited` (qml-rule.md §4.4 —
    `TextField.textEdited` takes no argument, unlike the widget-side
    signal, so simulating it by hand is the exact trap that section
    warns about)."""
    vm, _model = _vm_with_two_rows()
    quick, root = _load(qapp, vm)

    field = qml_item(root, "txtDatabaseStatusSearch")
    field.forceActiveFocus()
    QTest.keyClicks(quick, "30m")
    qapp.processEvents()

    assert vm.rowCount == 1
    assert qml_item(root, "databaseStatusSymbol_BTCUSDT_30m") is not None
    quick.close()
    quick.deleteLater()


def test_search_field_placeholder_matches_house_style(qapp, qml_item):
    vm, _model = _vm_with_two_rows()
    quick, root = _load(qapp, vm)

    field = qml_item(root, "txtDatabaseStatusSearch")

    assert field.property("placeholderText") == "Tìm symbol / khung thời gian…"
    quick.close()
    quick.deleteLater()


def test_row_count_badge_reflects_an_active_search_filter(qapp, qml_item):
    vm, _model = _vm_with_two_rows()
    quick, root = _load(qapp, vm)

    field = qml_item(root, "txtDatabaseStatusSearch")
    field.forceActiveFocus()
    QTest.keyClicks(quick, "1s")
    qapp.processEvents()

    badge = qml_item(root, "panelHeaderBadgeText")
    assert badge.property("text") == "1 shard"
    quick.close()
    quick.deleteLater()


def test_empty_state_message_shows_only_when_the_search_matches_nothing(qapp, qml_item):
    vm, _model = _vm_with_two_rows()
    quick, root = _load(qapp, vm)

    empty_label = qml_item(root, "lblDatabaseStatusEmpty")
    assert empty_label.property("visible") is False

    field = qml_item(root, "txtDatabaseStatusSearch")
    field.forceActiveFocus()
    QTest.keyClicks(quick, "nonexistent-symbol")
    qapp.processEvents()

    assert empty_label.property("visible") is True
    quick.close()
    quick.deleteLater()


def test_actions_disabled_when_vm_reports_not_idle(qapp, qml_item):
    vm, _model = _vm_with_two_rows()
    vm.setActionsEnabled(False)
    quick, root = _load(qapp, vm)

    for name in (
        "btnDatabaseStatusKlines_BTCUSDT_1s",
        "btnDatabaseStatusSync_BTCUSDT_1s",
        "btnDatabaseStatusClear_BTCUSDT_1s",
    ):
        assert qml_item(root, name).property("enabled") is False
    quick.close()
    quick.deleteLater()


def test_actions_re_enabled_when_vm_goes_back_to_idle(qapp, qml_item):
    vm, _model = _vm_with_two_rows()
    vm.setActionsEnabled(False)
    quick, root = _load(qapp, vm)

    vm.setActionsEnabled(True)
    qapp.processEvents()

    button = qml_item(root, "btnDatabaseStatusSync_BTCUSDT_1s")
    assert button.property("enabled") is True
    quick.close()
    quick.deleteLater()


def test_clicking_sync_while_disabled_does_not_request_the_action(qapp, qml_item):
    """A `Button` with `enabled: false` still exists in the scene, so a
    click must not need falling through to a Presenter guard — the row
    itself must refuse it, same as any other disabled Qt control."""
    vm, _model = _vm_with_two_rows()
    vm.setActionsEnabled(False)
    quick, root = _load(qapp, vm)
    requests: list[tuple[str, str, str]] = []
    vm.rowActionRequested.connect(lambda a, s, i: requests.append((a, s, i)))

    button = qml_item(root, "btnDatabaseStatusSync_BTCUSDT_1s")
    point = button.mapToScene(button.boundingRect().center())
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=point.toPoint())
    qapp.processEvents()

    assert requests == []
    quick.close()
    quick.deleteLater()
