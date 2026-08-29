import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Layout and bindings only (EPIC-015 §3.2). Body for a `QmlOverlay` host —
// no title bar, no close button: that chrome is `Overlay`'s (qml-rule.md
// §0.1/§0.2 — this widget is used from screens that are still QtWidgets
// today). All state, grouping, and the pin/current rules live in
// TimeframeVM (shared with `TimeframeToolbar.qml`); this file only reads
// `vm.*`/`Theme.*`.
ColumnLayout {
    id: root
    objectName: "timeframePickerBody"
    spacing: 14

    ScrollView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true

        ColumnLayout {
            width: parent.width
            spacing: 14

            Repeater {
                model: vm.groups

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            text: modelData.label
                            textFormat: Text.PlainText
                            color: Theme.muted
                            font.bold: true
                            font.pixelSize: 10
                            font.letterSpacing: 0.8
                        }
                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }
                        Text {
                            text: modelData.caption
                            textFormat: Text.PlainText
                            color: Theme.muted
                            font.pixelSize: 10
                        }
                    }

                    GridLayout {
                        columns: 6
                        columnSpacing: 8
                        rowSpacing: 8

                        Repeater {
                            model: modelData.rows
                            TimeframePickerCard {
                                code: modelData.code
                                label: modelData.label
                                pinned: modelData.pinned
                                current: modelData.current
                                onChosen: function(code) { vm.choose(code) }
                                onPinToggled: function(code) { vm.togglePinned(code) }
                            }
                        }
                    }
                }
            }
        }
    }

    Text {
        objectName: "lblTimeframeWarning"
        Layout.fillWidth: true
        visible: vm.hasWarning
        text: "Khung dưới 1 phút sinh rất nhiều nến — một ngày dữ liệu ở 1s là ~86.400 nến."
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
        color: Theme.muted
        font.pixelSize: 10
    }

    RowLayout {
        Layout.fillWidth: true
        Text {
            Layout.fillWidth: true
            text: "★ ghim lên thanh biểu đồ"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
        Text {
            objectName: "lblTimeframeCurrent"
            text: "Đang dùng: " + vm.currentCode
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
    }
}
