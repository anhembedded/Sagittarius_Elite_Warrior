import QtQuick
import QtQuick.Layouts
import "../kit"

// One row of the Database Status table. `symbol`/`interval`/`firstRecord`/
// `lastRecord`/`totalCandles`/`statusText`/`isHealthy` are role names read
// straight off `DatabaseStatusTableModel` (see database_status_vm.py) — this
// delegate does no lookup of its own.
//
// Every action button emits `vm.requestAction(...)` (wired to the real
// screen ViewModel at the composition-root level, NOTES.md) and is
// disabled while `vm.actionsEnabled` is false — mirrors the old
// `_StatusRowWidget.apply_ui_mode(idle)`, which disabled all four action
// buttons while a sync was running.
//
// Column widths are properties, not literals, so the header row in
// DatabaseStatusTable.qml and every delegate instance share one definition
// (qml-rule.md §6.3 — a table's columns must not drift out of sync between
// header and body).
//
// Action buttons are the shared `kit/Button` (retrofitted 2026-08-30) —
// `DatabaseStatusActionButton.qml` is retired, see `qml/kit/NOTES.md`.
Item {
    id: root
    implicitHeight: 40

    property int symbolWidth: 160
    property int tfWidth: 60
    property int statusWidth: 150
    property int actionsWidth: 230

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        spacing: 8

        Text {
            objectName: "databaseStatusSymbol_" + symbol + "_" + interval
            Layout.preferredWidth: root.symbolWidth
            text: symbol
            textFormat: Text.PlainText
            color: Theme.textPrimary
            font.bold: true
            font.pixelSize: 12
        }

        Rectangle {
            Layout.preferredWidth: root.tfWidth
            implicitHeight: 20
            radius: 4
            color: Theme.stateActiveTint
            border.width: 1
            border.color: Theme.accent
            Text {
                anchors.centerIn: parent
                text: interval
                textFormat: Text.PlainText
                color: Theme.accent
                font.pixelSize: 10
                font.bold: true
            }
        }

        Text {
            objectName: "databaseStatusFirstRecord_" + symbol + "_" + interval
            Layout.fillWidth: true
            // `Layout.minimumWidth: 0` is required alongside `elide` — a
            // fillWidth Text's minimum width otherwise defaults to its
            // *un-elided* implicitWidth (the full string's natural width),
            // so RowLayout could never actually shrink this column below
            // the length of a full ISO datetime, and it overflowed into the
            // `lastRecord` column next to it (BUG-076: the two strings
            // rendered on top of each other).
            Layout.minimumWidth: 0
            text: firstRecord
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: Theme.muted
            font.pixelSize: 11
        }

        Text {
            objectName: "databaseStatusLastRecord_" + symbol + "_" + interval
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: lastRecord
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: Theme.muted
            font.pixelSize: 11
        }

        RowLayout {
            Layout.preferredWidth: root.statusWidth
            spacing: 6
            Text {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignRight
                text: totalCandles
                textFormat: Text.PlainText
                color: Theme.textPrimary
                font.pixelSize: 11
            }
            Text {
                text: statusText
                textFormat: Text.PlainText
                color: isHealthy ? Theme.success : Theme.danger
                font.pixelSize: 11
            }
        }

        RowLayout {
            Layout.preferredWidth: root.actionsWidth
            spacing: 6
            Item { Layout.fillWidth: true }
            Button {
                objectName: "btnDatabaseStatusKlines_" + symbol + "_" + interval
                text: "KLines"
                role: "secondary"
                enabled: Boolean(vm && vm.actionsEnabled)
                onClicked: if (vm) vm.requestAction("klines", symbol, interval)
            }
            Button {
                objectName: "btnDatabaseStatusGaps_" + symbol + "_" + interval
                text: "Gaps"
                role: "danger"
                visible: !isHealthy
                enabled: Boolean(vm && vm.actionsEnabled)
                onClicked: if (vm) vm.requestAction("gaps", symbol, interval)
            }
            Button {
                objectName: "btnDatabaseStatusSync_" + symbol + "_" + interval
                text: "Sync"
                role: "secondary"
                enabled: Boolean(vm && vm.actionsEnabled)
                onClicked: if (vm) vm.requestAction("sync", symbol, interval)
            }
            Button {
                objectName: "btnDatabaseStatusClear_" + symbol + "_" + interval
                text: "Clear"
                role: "danger"
                enabled: Boolean(vm && vm.actionsEnabled)
                onClicked: if (vm) vm.requestAction("clear", symbol, interval)
            }
        }
    }
}
