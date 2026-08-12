import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

Popup {
    id: root
    width: 320
    padding: 0

    background: Rectangle {
        color: Theme.bgCard
        border.color: Theme.border
        radius: 6
    }

    contentItem: ColumnLayout {
        spacing: 0

        // Header
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            color: "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12

                Text {
                    text: "Thực thi tập lệnh"
                    color: Theme.textPrimary
                    font.pixelSize: 12
                    font.bold: true
                    Layout.fillWidth: true
                }

            }

            Rectangle {
                width: parent.width
                height: 1
                color: Theme.border
                anchors.bottom: parent.bottom
            }
        }

        // List
        ListView {
            id: listView
            Layout.fillWidth: true
            Layout.preferredHeight: contentHeight
            interactive: false
            
            // Only "On bar close" is real today (RunStaticBacktestCommandHandler
            // evaluates the strategy once per closed candle — BOT-021). The
            // other 3 need BOT-042 (tick-level engine support) before they mean
            // anything, so they're shown-but-disabled rather than hidden, per
            // BOT-022 §3: "ẩn/disable 3 lựa chọn còn lại thay vì hiện ra rồi
            // không hoạt động".
            model: ListModel {
                id: listModel
                ListElement { text: "On bar close"; checked: true; locked: true }
                ListElement { text: "Khi lệnh được khớp"; checked: false; locked: false }
                ListElement { text: "Trên mỗi tick của thanh lịch sử"; checked: false; locked: false }
                ListElement { text: "Trên mỗi tick của thanh thời gian thực"; checked: false; locked: false }
            }

            delegate: ItemDelegate {
                id: delegateItem
                width: listView.width
                height: 36
                enabled: !model.locked
                objectName: "chkExecutionTrigger_" + index

                background: Rectangle {
                    color: delegateItem.hovered ? "#17181d" : "transparent"
                }

                contentItem: RowLayout {
                    spacing: 10
                    opacity: delegateItem.enabled ? 1.0 : 0.4

                    CheckBox {
                        checked: model.checked
                        enabled: !model.locked
                        onCheckedChanged: model.checked = checked
                    }

                    Text {
                        text: model.text
                        color: Theme.textPrimary
                        font.pixelSize: 12
                        Layout.fillWidth: true
                    }

                    Image {
                        source: "image://icons/info/muted"
                        sourceSize: Qt.size(14, 14)
                    }
                }
            }
        }
    }
}
