import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// OrderExecutionModal (BOT-088) — Modal card for order execution trigger modes.
ModalDialogCard {
    id: root
    title: "THỰC THI TẬP LỆNH"
    iconSource: "image://icons/briefcase/accent"
    width: 400
    height: 250

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 4

        ListView {
            id: listView
            Layout.fillWidth: true
            Layout.fillHeight: true
            interactive: false

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
                height: 38
                enabled: !model.locked
                objectName: "chkExecutionTrigger_" + index

                background: Rectangle {
                    color: delegateItem.hovered ? "#1c1e2b" : "transparent"
                    radius: 6
                }

                contentItem: RowLayout {
                    spacing: 10
                    opacity: delegateItem.enabled ? 1.0 : 0.45

                    CheckBox {
                        checked: model.checked
                        enabled: !model.locked
                        onCheckedChanged: model.checked = checked
                    }

                    Text {
                        text: model.text
                        color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
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
