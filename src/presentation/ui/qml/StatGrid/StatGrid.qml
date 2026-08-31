import QtQuick

// Layout only. `tone` -> colour is the one lookup this file is allowed to
// do — it is presentation, not a business rule, and every value comes from
// Theme (EPIC-015 §3.3).
// No `width: parent.width` here (BUG-071): this file is always loaded as a
// `QmlOverlay`'s `QQuickWidget` root object, which has no QML `parent` —
// `SizeRootObjectToView` sets this item's width directly instead.
Grid {
    id: root
    objectName: "statGrid"
    columns: 2
    columnSpacing: 12
    rowSpacing: 12

    // Same map as `kit/style.py`'s TONE_COLOUR_KEYS: POSITIVE -> success,
    // NEGATIVE -> danger. Named `success`/`danger` in Theme, not
    // `positive`/`negative` — checked against the real token dict before
    // shipping, not assumed (EPIC-015's render-time-error lesson, applied
    // to itself).
    function toneColour(tone) {
        if (tone === "POSITIVE") return Theme.success
        if (tone === "NEGATIVE") return Theme.danger
        return Theme.textPrimary
    }

    Repeater {
        model: vm.cards

        Rectangle {
            objectName: "statCard_" + index
            width: (root.width - root.columnSpacing) / 2
            height: 76
            radius: 6
            color: Theme.bgCardHeader
            border.width: 1
            border.color: Theme.stateNavBorder

            Column {
                anchors.centerIn: parent
                spacing: 4
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: modelData.title
                    color: Theme.muted
                    font.pixelSize: 10
                }
                Row {
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 2
                    Text {
                        text: modelData.value
                        color: root.toneColour(modelData.tone)
                        font.bold: true
                        font.pixelSize: 16
                    }
                    Text {
                        visible: modelData.suffix !== ""
                        text: modelData.suffix
                        color: Theme.muted
                        font.pixelSize: 11
                    }
                }
            }
        }
    }
}
