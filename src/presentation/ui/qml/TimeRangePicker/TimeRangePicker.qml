import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Layout and bindings only (EPIC-015 §3.2). Body for a `QmlOverlay` host —
// no title bar, no Hủy/Áp dụng: that chrome is `Overlay`'s (qml-rule.md
// §0.1 — this widget is used from screens that are still QtWidgets today,
// unlike SymbolPicker, which deliberately stays outside QmlOverlay).
// All state, calendar math, and the preset/summary rules live in
// TimeRangePickerVM; this file only reads `vm.*`/`Theme.*`.
RowLayout {
    id: root
    objectName: "timeRangePickerBody"
    spacing: 18

    ColumnLayout {
        Layout.preferredWidth: 160
        Layout.fillHeight: true
        spacing: 4
        objectName: "timeRangePresets"

        Repeater {
            model: vm.presets
            Rectangle {
                objectName: "timeRangePreset_" + modelData.id
                Layout.fillWidth: true
                height: 32
                radius: 8
                color: modelData.selected ? Theme.stateActiveTint : "transparent"
                border.width: modelData.selected ? 1 : 0
                border.color: Theme.accent

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.label
                    textFormat: Text.PlainText
                    color: modelData.selected ? Theme.textPrimary : Theme.muted
                    font.pixelSize: 12
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: vm.choosePreset(modelData.id)
                }
            }
        }

        Item { Layout.fillHeight: true }
    }

    ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            ToolButton {
                objectName: "btnTimeRangePrev"
                text: "‹"
                onClicked: vm.pageMonths(-1)
            }

            TimeRangePickerMonth {
                objectName: "timeRangeLeftMonth"
                Layout.fillWidth: true
                monthLabel: vm.leftMonthLabel
                days: vm.leftDays
                weekdayLabels: vm.weekdayLabels
                onDayClicked: function(iso) { vm.selectDay(iso) }
            }

            TimeRangePickerMonth {
                objectName: "timeRangeRightMonth"
                Layout.fillWidth: true
                monthLabel: vm.rightMonthLabel
                days: vm.rightDays
                weekdayLabels: vm.weekdayLabels
                onDayClicked: function(iso) { vm.selectDay(iso) }
            }

            ToolButton {
                objectName: "btnTimeRangeNext"
                text: "›"
                onClicked: vm.pageMonths(1)
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Text {
                    text: "TỪ"
                    textFormat: Text.PlainText
                    color: Theme.muted
                    font.pixelSize: 10
                    font.letterSpacing: 0.8
                }
                TextField {
                    id: fromField
                    objectName: "txtRangeFrom"
                    Layout.fillWidth: true
                    text: vm.fromText
                    color: Theme.textPrimary
                    selectByMouse: true
                    onEditingFinished: vm.setFromText(text)
                    background: Rectangle {
                        color: Theme.bg
                        border.width: 1
                        border.color: fromField.activeFocus ? Theme.accent : Theme.stateNavBorder
                        radius: 6
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Text {
                    text: "ĐẾN"
                    textFormat: Text.PlainText
                    color: Theme.muted
                    font.pixelSize: 10
                    font.letterSpacing: 0.8
                }
                TextField {
                    id: toField
                    objectName: "txtRangeTo"
                    Layout.fillWidth: true
                    text: vm.toText
                    color: Theme.textPrimary
                    selectByMouse: true
                    onEditingFinished: vm.setToText(text)
                    background: Rectangle {
                        color: Theme.bg
                        border.width: 1
                        border.color: toField.activeFocus ? Theme.accent : Theme.stateNavBorder
                        radius: 6
                    }
                }
            }
        }

        Text {
            objectName: "lblRangeSummary"
            Layout.fillWidth: true
            text: vm.summaryText
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 11
        }
    }
}
