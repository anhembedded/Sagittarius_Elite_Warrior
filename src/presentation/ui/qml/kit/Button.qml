import QtQuick

// Shared button — exactly 4 kinds. Design spec 2026-08-30: primary = accent
// outline, secondary = neutral outline, ghost = text only, danger = red
// outline. 30px tall, 6px radius. ("Was: gold fill, green outline, red fill
// and bare text all on one screen.")
//
// Deliberately its own colour scheme, not a QML port of `kit/style.py`'s
// `StyledButton` — that QtWidgets component fills Primary/Danger solid
// rather than outlining them, which is the exact inconsistency this spec
// exists to replace (qml-rule.md §0.2 — a feature that does not fit gets a
// design change, not a patch). `enabled` is `Item`'s own built-in property,
// not redeclared here.
Rectangle {
    id: root
    objectName: "button"

    property string text: ""
    //: "primary" | "secondary" | "ghost" | "danger"
    property string role: "secondary"
    signal clicked()

    implicitWidth: label.implicitWidth + 24
    implicitHeight: 30
    radius: 6
    color: hoverArea.containsMouse && root.enabled ? Theme.stateHoverBg : "transparent"
    border.width: root.role === "ghost" ? 0 : 1
    border.color: {
        if (!root.enabled) return Theme.muted;
        if (root.role === "primary") return Theme.accent;
        if (root.role === "danger") return Theme.danger;
        if (root.role === "secondary") return Theme.stateNavBorder;
        return "transparent";
    }

    Text {
        id: label
        objectName: "buttonLabel"
        anchors.centerIn: parent
        anchors.margins: 12
        text: root.text
        textFormat: Text.PlainText
        font.pixelSize: 11
        font.bold: root.role === "primary" || root.role === "danger"
        color: {
            if (!root.enabled) return Theme.muted;
            if (root.role === "primary") return Theme.accent;
            if (root.role === "danger") return Theme.danger;
            if (root.role === "ghost") return Theme.muted;
            return Theme.textPrimary;
        }
    }

    MouseArea {
        id: hoverArea
        anchors.fill: parent
        enabled: root.enabled
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
