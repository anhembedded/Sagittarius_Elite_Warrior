import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

BaseCard {
    id: root
    implicitWidth: 250
    implicitHeight: 75
    color: Theme.bgCard
    border.color: Theme.border
    border.width: 1
    radius: 4

    property string title: ""
    property string value: "0.00"
    property color valueColor: Theme.textPrimary
    property string suffix: ""
    property string badgeText: ""
    property color badgeBgColor: "transparent"
    property color badgeTextColor: Theme.muted

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        anchors.topMargin: 10
        anchors.bottomMargin: 10
        spacing: 4

        // Row 1: Title & Icon
        RowLayout {
            spacing: 6
            Text {
                text: root.title
                color: Theme.muted
                font.pixelSize: 12
            }
            // Info icon
            Image {
                source: "image://icons/info/muted"
                sourceSize: Qt.size(13, 13)
                Layout.alignment: Qt.AlignVCenter
            }
            Item { Layout.fillWidth: true }
        }

        // Row 2: Values & Badges
        RowLayout {
            spacing: 6
            Text {
                text: root.value
                color: root.valueColor
                font.pixelSize: 18
                font.bold: true
            }
            
            Text {
                text: root.suffix
                color: Theme.muted
                font.pixelSize: 10
                visible: root.suffix !== ""
                Layout.alignment: Qt.AlignBottom
                Layout.bottomMargin: 3
            }
            
            Rectangle {
                visible: root.badgeText !== ""
                color: root.badgeBgColor
                radius: 4
                implicitWidth: badgeTextItem.implicitWidth + 10
                implicitHeight: badgeTextItem.implicitHeight + 6
                Layout.alignment: Qt.AlignVCenter
                
                Text {
                    id: badgeTextItem
                    anchors.centerIn: parent
                    text: root.badgeText
                    color: root.badgeTextColor
                    font.pixelSize: 11
                }
            }
            
            Item { Layout.fillWidth: true }
        }
    }
}
