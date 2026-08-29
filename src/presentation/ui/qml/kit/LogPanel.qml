import QtQuick
import QtQuick.Layouts

// Shared log panel — one component for System Monitor, Sync Log, and
// "Nhật ký Backtest" (`AppLogPanel` in QtWidgets today serves the same
// three; this is its QML equivalent, not a fourth copy). Design spec
// 2026-08-30: header + count badge + Copy/Clear, monospace body, muted
// timestamps. ("Was: three different headers, two type sizes, count tag
// styled twice.")
//
// `model` expects a plain list of `{timestampText, message, isError}` dicts
// — a host reading a real `QAbstractListModel` (`runtime.log_list_model.
// LogListModel`, per `kit/surfaces/log_panel.py`) converts to this shape
// first, same "structural pass" boundary every other widget built this
// session uses (see NOTES.md).
ColumnLayout {
    id: root
    objectName: "logPanel"
    spacing: 8

    property string title: ""
    property int count: 0
    property alias model: logList.model
    signal copyRequested()
    signal clearRequested()

    PanelHeader {
        Layout.fillWidth: true
        title: root.title
        badgeText: root.count + " EVENTS"

        Button {
            objectName: "btnLogPanelCopy"
            text: "Copy"
            role: "ghost"
            onClicked: root.copyRequested()
        }
        Button {
            objectName: "btnLogPanelClear"
            text: "Clear"
            role: "ghost"
            onClicked: root.clearRequested()
        }
    }

    ListView {
        id: logList
        objectName: "logPanelList"
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        reuseItems: true
        delegate: RowLayout {
            width: logList.width
            spacing: 8

            Text {
                text: "[" + modelData.timestampText + "]"
                textFormat: Text.PlainText
                font.family: "monospace"
                font.pixelSize: 11
                color: Theme.muted
            }
            Text {
                Layout.fillWidth: true
                text: modelData.message
                textFormat: Text.PlainText
                font.family: "monospace"
                font.pixelSize: 11
                color: modelData.isError ? Theme.danger : Theme.textPrimary
                elide: Text.ElideRight
            }
        }
    }
}
