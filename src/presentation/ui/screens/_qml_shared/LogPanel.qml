import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Reusable log panel (BOT-030 Phase 3). Shared by the Database sync log and
// the Dev Board system monitor — both show the same timestamped, leveled
// lines, so they share one component instead of two near-identical copies.
//
// Usage:
//     LogPanel { title: "SYSTEM MONITOR"; logModel: viewModel.logModel }
Rectangle {
    id: root

    property string title: "LOG"
    property alias logModel: logList.model
    property bool autoScroll: true

    color: Theme.bgCard
    border.color: Theme.border
    border.width: 1
    radius: 8

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---- Header ----------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            color: Theme.bgCardHeader
            radius: 8

            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: parent.radius
                color: parent.color
            }
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: Theme.border
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                Text {
                    text: root.title
                    color: Theme.accent
                    font.pixelSize: 12
                    font.bold: true
                }

                Rectangle {
                    radius: 3
                    color: "#17181d"
                    border.color: Theme.border
                    border.width: 1
                    Layout.preferredWidth: countText.implicitWidth + 12
                    Layout.preferredHeight: 18
                    Text {
                        id: countText
                        anchors.centerIn: parent
                        text: logList.count + " EVENTS"
                        color: Theme.muted
                        font.pixelSize: 9
                        font.bold: true
                    }
                }

                Item { Layout.fillWidth: true }

                Button {
                    id: clearButton
                    objectName: "btnClearLog"
                    text: "Clear"
                    implicitHeight: 24
                    // Clearing the on-screen log is a pure UI concern — no
                    // Presenter round-trip, same as MonitorCard did.
                    onClicked: logList.model.clear()

                    contentItem: RowLayout {
                        spacing: 4
                        Image {
                            source: "image://icons/trash-2/muted"
                            sourceSize.width: 12
                            sourceSize.height: 12
                            Layout.preferredWidth: 12
                            Layout.preferredHeight: 12
                        }
                        Text {
                            text: clearButton.text
                            color: Theme.textPrimary
                            font.pixelSize: 11
                        }
                    }

                    background: Rectangle {
                        implicitWidth: 64
                        radius: 4
                        color: clearButton.hovered ? "#1f2127" : "#17181d"
                        border.color: Theme.border
                        border.width: 1
                    }
                }
            }
        }

        // ---- Lines -----------------------------------------------------
        ListView {
            id: logList
            objectName: "logList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 8
            clip: true
            spacing: 2

            // Follows the newest line, but only while the user is already at
            // the bottom — otherwise scrolling back to read history would be
            // yanked away on every new message.
            onCountChanged: if (root.autoScroll && atYEnd) positionViewAtEnd()

            ScrollBar.vertical: ScrollBar {}

            delegate: RowLayout {
                width: ListView.view.width
                spacing: 6

                Image {
                    source: "image://icons/" + model.icon + "/"
                            + (model.level === "error" ? "danger"
                               : model.level === "success" ? "success" : "muted")
                    sourceSize.width: 12
                    sourceSize.height: 12
                    Layout.preferredWidth: 12
                    Layout.preferredHeight: 12
                    Layout.alignment: Qt.AlignTop
                    Layout.topMargin: 2
                }

                Text {
                    text: "[" + model.timestamp + "]"
                    color: Theme.muted
                    font.family: "Consolas"
                    font.pixelSize: 11
                    Layout.alignment: Qt.AlignTop
                }

                Text {
                    text: model.message
                    color: model.level === "error" ? Theme.danger : Theme.textPrimary
                    font.family: "Consolas"
                    font.pixelSize: 11
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    Layout.fillWidth: true
                }
            }
        }
    }
}
