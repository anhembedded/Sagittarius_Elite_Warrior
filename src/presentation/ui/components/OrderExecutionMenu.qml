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

                Text {
                    text: "Đặt lại"
                    color: Theme.muted
                    font.pixelSize: 11
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            // Reset logic
                            for (var i = 0; i < listModel.count; ++i) {
                                listModel.setProperty(i, "checked", false)
                            }
                        }
                    }
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
            
            model: ListModel {
                id: listModel
                ListElement { text: "On bar close"; checked: true }
                ListElement { text: "Khi lệnh được khớp"; checked: true }
                ListElement { text: "Trên mỗi tick của thanh lịch sử"; checked: false }
                ListElement { text: "Trên mỗi tick của thanh thời gian thực"; checked: false }
            }

            delegate: ItemDelegate {
                width: listView.width
                height: 36
                
                background: Rectangle {
                    color: parent.hovered ? "#17181d" : "transparent"
                }

                contentItem: RowLayout {
                    spacing: 10
                    
                    CheckBox {
                        checked: model.checked
                        onCheckedChanged: model.checked = checked
                        // We rely on standard CheckBox styling here, may need custom style for strict design match
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
                
                onClicked: {
                    model.checked = !model.checked
                }
            }
        }
    }
}
