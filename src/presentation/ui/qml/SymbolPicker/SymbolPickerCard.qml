import QtQuick
import QtQuick.Shapes

// Reusable symbol-card Component. It renders one VM row and dispatches the
// two user intents separately: choose or toggle favourite.
Item {
    id: root
    objectName: "symbolCard_" + root.symbol
    property string symbol: ""
    property string base: ""
    property string quote: ""
    property string subtitle: ""
    property bool favourite: false
    property bool current: false
    property bool focused: false
    property var vm
    property var theme

    width: GridView.view ? GridView.view.cellWidth : (parent.width - 16) / 3
    height: GridView.view ? GridView.view.cellHeight - 8 : Math.max(50, cardColumn.implicitHeight + 16)

    Rectangle {
        id: card
        anchors.fill: parent
        color: root.focused ? root.theme.stateActiveTint : cardHover.hovered ? root.theme.stateHoverBg : root.theme.bgCardHeader
        border.width: 1
        border.color: root.current || root.focused ? root.theme.accent : root.theme.stateNavBorder
        radius: 6

        HoverHandler { id: cardHover }

        Column {
            id: cardColumn
            anchors.left: parent.left
            anchors.leftMargin: 10
            anchors.right: starButton.left
            anchors.rightMargin: 4
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2
            Row {
                spacing: 0
                Text {
                    text: root.base
                    textFormat: Text.PlainText
                    color: root.theme.textPrimary
                    font.bold: true
                    font.pixelSize: 12
                }
                Text {
                    text: root.quote
                    textFormat: Text.PlainText
                    color: root.theme.muted
                    font.pixelSize: 12
                }
            }
            Text {
                text: root.subtitle
                textFormat: Text.PlainText
                color: root.theme.muted
                font.pixelSize: 10
            }
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: root.vm.choose(root.symbol)
        }

        Rectangle {
            id: starButton
            objectName: "symbolStar_" + root.symbol
            z: 1
            anchors.right: parent.right
            anchors.rightMargin: 6
            anchors.verticalCenter: parent.verticalCenter
            width: 24
            height: 24
            color: "transparent"

            Shape {
                anchors.centerIn: parent
                width: 18
                height: 18
                ShapePath {
                    fillColor: root.favourite ? root.theme.accent : "transparent"
                    strokeColor: root.favourite ? root.theme.accent : root.theme.muted
                    strokeWidth: 1
                    startX: 9
                    startY: 1
                    PathLine { x: 11.4; y: 6.4 }
                    PathLine { x: 17.2; y: 6.8 }
                    PathLine { x: 12.8; y: 10.6 }
                    PathLine { x: 14.2; y: 16.5 }
                    PathLine { x: 9; y: 13.3 }
                    PathLine { x: 3.8; y: 16.5 }
                    PathLine { x: 5.2; y: 10.6 }
                    PathLine { x: 0.8; y: 6.8 }
                    PathLine { x: 6.6; y: 6.4 }
                    PathLine { x: 9; y: 1 }
                }
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.vm.toggleFavourite(root.symbol)
            }
        }
    }
}
