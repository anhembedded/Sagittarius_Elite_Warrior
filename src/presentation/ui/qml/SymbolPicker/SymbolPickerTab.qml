import QtQuick

// Reusable filter-tab Component. It owns only visual state and emits an
// intent; SymbolPickerVM owns the selected scope/quote rules.
Rectangle {
    id: root
    objectName: "symbolPickerTab_" + root.tabData.id
    implicitWidth: tabLabel.implicitWidth + 20
    height: 30
    radius: 5

    property var tabData: ({})
    property var theme
    signal activated(string tabId)

    color: root.tabData.selected ? root.theme.stateActiveTint : root.theme.bg
    border.width: 1
    border.color: root.tabData.selected ? root.theme.accent : root.theme.stateNavBorder

    Text {
        id: tabLabel
        anchors.centerIn: parent
        text: root.tabData.label + (root.tabData.badge !== "" ? " · " + root.tabData.badge : "")
        textFormat: Text.PlainText
        color: root.tabData.selected ? root.theme.accent : root.theme.muted
        font.pixelSize: 11
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.activated(root.tabData.id)
    }
}
