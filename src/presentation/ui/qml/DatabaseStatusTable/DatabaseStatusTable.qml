import QtQuick
import QtQuick.Layouts
import "../kit"

// Layout and bindings only (EPIC-015 §3.2). Renders `DatabaseStatusVM`'s
// real production model (`DatabaseStatusTableModel`) — structural pass only:
// no search box, no wired row actions yet (NOTES.md). Body for a
// `QmlOverlay`-style host, but this widget is table content rather than a
// modal — whichever screen embeds it owns its own chrome.
//
// Header is the shared `kit/PanelHeader` (retrofitted 2026-08-30, see
// `qml/kit/NOTES.md`) — not a hand-rolled accent bar + label anymore.
ColumnLayout {
    id: root
    objectName: "databaseStatusBody"
    spacing: 10

    readonly property int symbolColumnWidth: 160
    readonly property int tfColumnWidth: 60
    readonly property int statusColumnWidth: 150
    readonly property int actionsColumnWidth: 230

    PanelHeader {
        Layout.fillWidth: true
        title: "Database Status"
        badgeText: vm.rowCount + " shard" + (vm.rowCount === 1 ? "" : "s")
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8

        Text {
            Layout.preferredWidth: root.symbolColumnWidth
            text: "SYMBOL"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
            font.letterSpacing: 0.8
        }
        Text {
            Layout.preferredWidth: root.tfColumnWidth
            text: "TF"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
            font.letterSpacing: 0.8
        }
        Text {
            Layout.fillWidth: true
            text: "FIRST RECORD"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
            font.letterSpacing: 0.8
        }
        Text {
            Layout.fillWidth: true
            text: "LAST RECORD"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
            font.letterSpacing: 0.8
        }
        Text {
            Layout.preferredWidth: root.statusColumnWidth
            horizontalAlignment: Text.AlignRight
            text: "TOTAL STATUS"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
            font.letterSpacing: 0.8
        }
        Text {
            Layout.preferredWidth: root.actionsColumnWidth
            horizontalAlignment: Text.AlignRight
            text: "ACTIONS"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
            font.letterSpacing: 0.8
        }
    }

    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

    ListView {
        id: rowsView
        objectName: "databaseStatusRows"
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        spacing: 2
        model: vm.rowsModel
        delegate: DatabaseStatusRow {
            width: rowsView.width
            symbolWidth: root.symbolColumnWidth
            tfWidth: root.tfColumnWidth
            statusWidth: root.statusColumnWidth
            actionsWidth: root.actionsColumnWidth
        }
    }

    Text {
        objectName: "lblDatabaseStatusFooter"
        Layout.fillWidth: true
        horizontalAlignment: Text.AlignHCenter
        text: "Scan a symbol to list more shards"
        textFormat: Text.PlainText
        color: Theme.muted
        font.pixelSize: 10
    }
}
