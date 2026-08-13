import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

BaseCard {
    id: root
    implicitWidth: 250
    implicitHeight: 80
    color: "#14161f"
    border.color: "#232634"
    border.width: 1
    radius: 8

    property string title: ""
    property string value: "0.00"
    property color valueColor: Theme.textPrimary
    property string suffix: ""
    property string badgeText: ""
    property color badgeBgColor: "transparent"
    property color badgeTextColor: Theme.muted

    // Hover effect for subtle visual feedback
    property bool isHovered: mouseArea.containsMouse

    Rectangle {
        anchors.fill: parent
        radius: 8
        color: root.isHovered ? "#1a1d29" : "transparent"
        border.color: root.isHovered ? "#363a4d" : "transparent"
        border.width: 1
        Behavior on color { ColorAnimation { duration: 150 } }
        Behavior on border.color { ColorAnimation { duration: 150 } }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        anchors.topMargin: 12
        anchors.bottomMargin: 12
        spacing: 6

        // Row 1: Title & Info Icon
        RowLayout {
            spacing: 6
            Text {
                text: root.title.toUpperCase()
                color: Theme.muted
                font.pixelSize: 10
                font.bold: true
                font.letterSpacing: 0.8
                Layout.alignment: Qt.AlignVCenter
            }
            // Info icon
            Image {
                source: "image://icons/info/muted"
                sourceSize: Qt.size(12, 12)
                Layout.alignment: Qt.AlignVCenter
                opacity: 0.7
            }
            Item { Layout.fillWidth: true }
        }

        // Row 2: Value Display & Badges
        RowLayout {
            spacing: 6
            Text {
                text: root.value
                color: root.valueColor
                font.pixelSize: 20
                font.bold: true
                font.family: "Inter, Segoe UI, sans-serif"
                Layout.alignment: Qt.AlignVCenter
            }
            
            Text {
                text: root.suffix
                color: Theme.muted
                font.pixelSize: 11
                font.bold: true
                visible: root.suffix !== ""
                Layout.alignment: Qt.AlignBottom
                Layout.bottomMargin: 3
            }
            
            Rectangle {
                visible: root.badgeText !== ""
                color: root.badgeBgColor
                radius: 4
                implicitWidth: badgeTextItem.implicitWidth + 12
                implicitHeight: badgeTextItem.implicitHeight + 6
                Layout.alignment: Qt.AlignVCenter
                
                Text {
                    id: badgeTextItem
                    anchors.centerIn: parent
                    text: root.badgeText
                    color: root.badgeTextColor
                    font.pixelSize: 11
                    font.bold: true
                }
            }
            
            Item { Layout.fillWidth: true }
        }
    }
}

