import QtQuick

// One grid cell: code + label, current highlight, and the pin star this
// mockup adds — toggling it updates `vm.pinnedRows`, which
// `TimeframeToolbar.qml`'s pill row reads (NOTES.md). Pure layout; every
// flag is read off the row TimeframeVM already computed.
//
// The whole-card MouseArea is declared before the star, so the star's own
// (smaller, later-declared) MouseArea paints on top and wins the hit test
// in its own corner — declaring them the other way round would let the
// card-wide area swallow every star click.
Rectangle {
    id: root
    property string code: ""
    property string label: ""
    property bool pinned: false
    property bool current: false
    signal chosen(string code)
    signal pinToggled(string code)

    objectName: "timeframeCard_" + root.code
    implicitWidth: 96
    implicitHeight: 52
    radius: 8
    color: root.current ? Theme.stateActiveTint : Theme.stateIdleBg
    border.width: 1
    border.color: root.current ? Theme.accent : Theme.stateNavBorder

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.chosen(root.code)
    }

    Text {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.margins: 8
        text: root.code
        textFormat: Text.PlainText
        color: root.current ? Theme.accent : Theme.textPrimary
        font.bold: true
        font.pixelSize: 13
    }

    Text {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 8
        text: root.label
        textFormat: Text.PlainText
        color: Theme.muted
        font.pixelSize: 10
    }

    Text {
        objectName: "timeframeStar_" + root.code
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 6
        text: root.pinned ? "★" : "☆"
        textFormat: Text.PlainText
        color: root.pinned ? Theme.accent : Theme.muted
        font.pixelSize: 13

        MouseArea {
            anchors.fill: parent
            anchors.margins: -4
            cursorShape: Qt.PointingHandCursor
            onClicked: root.pinToggled(root.code)
        }
    }
}
