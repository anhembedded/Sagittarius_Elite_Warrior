import QtQuick
import QtQuick.Layouts

// Shared panel header — one definition instead of every widget hand-rolling
// its own header row. Design spec 2026-08-30: accent mark, uppercase label,
// optional count badge, ghost actions on the right. ("Was: accent bar on
// some, none on others; three label sizes.")
//
// `font.pixelSize` is an int property in QML; the spec's "10.5px" rounds to
// `Palette.FONT_SIZE_SM` (11px, the app's real small-text token) rather than
// introducing a new fractional literal nothing else in the app uses.
RowLayout {
    id: root
    implicitHeight: 34
    spacing: 8

    property string title: ""
    property string badgeText: ""
    default property alias actions: actionsRow.data

    Rectangle {
        width: 2
        height: 14
        color: Theme.accent
    }

    Text {
        objectName: "panelHeaderTitle"
        text: root.title.toUpperCase()
        textFormat: Text.PlainText
        color: Theme.textPrimary
        font.bold: true
        font.pixelSize: 11
        font.letterSpacing: 0.8
    }

    Rectangle {
        objectName: "panelHeaderBadge"
        visible: root.badgeText !== ""
        radius: 10
        color: Theme.stateActiveTint
        implicitWidth: badgeLabel.implicitWidth + 14
        implicitHeight: 18

        Text {
            id: badgeLabel
            objectName: "panelHeaderBadgeText"
            anchors.centerIn: parent
            text: root.badgeText
            textFormat: Text.PlainText
            color: Theme.accent
            font.pixelSize: 10
            font.bold: true
        }
    }

    Item { Layout.fillWidth: true }

    Row {
        id: actionsRow
        objectName: "panelHeaderActions"
        spacing: 6
    }
}
