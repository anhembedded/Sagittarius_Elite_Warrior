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
            text: "StatCard"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
        Row {
            spacing: 10
            Rectangle {
                width: 220; height: 90; radius: 8
                color: Theme.bgCard; border.width: 1; border.color: Theme.border
                StatCard {
                    objectName: "previewNetPnlCard"
                    anchors.fill: parent
                    anchors.margins: 14
                    title: "Tổng lãi/lỗ (net pnl)"
                    value: "-8,193.54 USD"
                    caption: "-81.94%"
                    tone: "negative"
                }
            }
            Rectangle {
                width: 220; height: 90; radius: 8
                color: Theme.bgCard; border.width: 1; border.color: Theme.border
                StatCard {
                    objectName: "previewWinRateCard"
                    anchors.fill: parent
                    anchors.margins: 14
                    title: "Tỷ lệ thắng"
                    value: "10.33%"
                    caption: "92/891 lệnh"
                }
            }
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 8
        Text {
            text: "StatusPill"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
        Row {
            spacing: 8
            StatusPill { objectName: "previewIdlePill"; text: "WS: IDLE"; tone: "idle" }
            StatusPill { objectName: "previewActivePill"; text: "WS: SYNCING"; tone: "active" }
            StatusPill { objectName: "previewSuccessPill"; text: "WS: LIVE"; tone: "success" }
            StatusPill { objectName: "previewDangerPill"; text: "WS: ERROR"; tone: "danger" }
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 8
        Text {
            text: "ProgressBanner"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 60
            color: Theme.bgCard
            border.width: 1
            border.color: Theme.border
            radius: 8
            ProgressBanner {
                anchors.fill: parent
                anchors.margins: 12
                statusText: "Đang chạy backtest…"
                percent: 62
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
