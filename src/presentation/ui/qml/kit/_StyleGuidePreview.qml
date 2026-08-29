import QtQuick
import QtQuick.Layouts

// Preview-only composition of the four `kit/` components, side by side —
// not itself part of the shared kit (leading underscore, same convention
// preview-only helpers elsewhere in this repo use). See NOTES.md.
ColumnLayout {
    id: root
    width: 720
    spacing: 20

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 8
        Text {
            text: "PanelHeader"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 44
            color: Theme.bgCard
            border.width: 1
            border.color: Theme.border
            radius: 8
            PanelHeader {
                anchors.fill: parent
                anchors.margins: 6
                title: "System Controls"
                badgeText: ""
            }
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 8
        Text {
            text: "Button — 4 kinds"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
        Row {
            spacing: 8
            Button { objectName: "previewPrimary"; text: "▷ Start Live"; role: "primary" }
            Button { objectName: "previewSecondary"; text: "Load History"; role: "secondary" }
            Button { objectName: "previewGhost"; text: "Copy"; role: "ghost" }
            Button { objectName: "previewDanger"; text: "Xóa toàn bộ Vault"; role: "danger" }
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 8
        Text {
            text: "LogPanel"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 140
            color: Theme.bgCard
            border.width: 1
            border.color: Theme.border
            radius: 8
            LogPanel {
                anchors.fill: parent
                anchors.margins: 10
                title: "System Monitor"
                count: previewLogModel.length
                model: previewLogModel
            }
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 8
        Text {
            text: "DialogShell"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 160
            color: Theme.bgCard
            border.width: 1
            border.color: Theme.border
            radius: 8
            DialogShell {
                anchors.fill: parent
                anchors.margins: 10
                title: "Dialog Title"
                showFooter: true
                Text {
                    anchors.fill: parent
                    text: "list · fields · grid — one body, three fills"
                    textFormat: Text.PlainText
                    color: Theme.muted
                    font.pixelSize: 11
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }
}
