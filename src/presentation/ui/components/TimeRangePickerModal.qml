import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.UI 1.0

// TimeRangePickerModal — Modal dialog for picking backtest time range preset or custom start/end dates.
ModalDialogCard {
    id: root
    title: "KHOẢNG THỜI GIAN BACKTEST"
    iconSource: "image://icons/calendar/accent"
    preferredWidth: 440
    preferredHeight: (root.hasViewModel && viewModel.timeRangePreset === "custom") ? 410 : 330

    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

    ScrollView {
        anchors.fill: parent
        anchors.margins: 14
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: root.width - 48
            spacing: 8

            Repeater {
                model: root.hasViewModel ? viewModel.timeRangePresetOptions : []

                ItemDelegate {
                    id: delegateItem
                    Layout.fillWidth: true
                    implicitHeight: 40
                    required property var modelData
                    required property int index

                    readonly property bool isSelected: root.hasViewModel && modelData.value === viewModel.timeRangePreset

                    background: Rectangle {
                        color: delegateItem.isSelected ? "#242738" : (delegateItem.hovered ? "#181a24" : "transparent")
                        border.color: delegateItem.isSelected ? (Theme && Theme.accent ? Theme.accent : "#f0b90b") : (Theme && Theme.border ? Theme.border : "#2a2d3e")
                        border.width: 1
                        radius: 8
                    }

                    contentItem: RowLayout {
                        spacing: 12
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12

                        Image {
                            source: "image://icons/calendar/accent"
                            sourceSize: Qt.size(14, 14)
                            opacity: delegateItem.isSelected ? 1.0 : 0.6
                        }

                        Text {
                            text: delegateItem.modelData.label
                            color: delegateItem.isSelected ? (Theme && Theme.accent ? Theme.accent : "#f0b90b") : (Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb")
                            font.pixelSize: 12
                            font.bold: delegateItem.isSelected
                            Layout.fillWidth: true
                        }

                        Rectangle {
                            visible: delegateItem.isSelected
                            implicitWidth: 8
                            implicitHeight: 8
                            radius: 4
                            color: Theme && Theme.accent ? Theme.accent : "#f0b90b"
                        }
                    }

                    onClicked: {
                        if (root.hasViewModel) {
                            viewModel.timeRangePreset = modelData.value
                        }
                        if (modelData.value !== "custom") {
                            root.close()
                        }
                    }
                }
            }

            // Custom Range inputs
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8
                visible: root.hasViewModel && viewModel.timeRangePreset === "custom"

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                    Layout.topMargin: 4
                    Layout.bottomMargin: 4
                }

                Text {
                    text: "Nhập khoảng ngày tùy chỉnh:"
                    color: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
                    font.pixelSize: 11
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    DateTimePicker {
                        objectName: "txtBacktestRangeStart"
                        Layout.fillWidth: true
                        text: root.hasViewModel ? viewModel.customStartText : ""
                        placeholderText: "Từ yyyy-MM-dd HH:mm"
                        onTextEdited: (text) => { if (root.hasViewModel) viewModel.customStartText = text }
                    }

                    DateTimePicker {
                        objectName: "txtBacktestRangeEnd"
                        Layout.fillWidth: true
                        text: root.hasViewModel ? viewModel.customEndText : ""
                        placeholderText: "Đến yyyy-MM-dd HH:mm"
                        onTextEdited: (text) => { if (root.hasViewModel) viewModel.customEndText = text }
                    }
                }

                Button {
                    Layout.alignment: Qt.AlignRight
                    text: "Áp dụng"
                    implicitWidth: 100
                    implicitHeight: 32
                    background: Rectangle {
                        color: Theme && Theme.accent ? Theme.accent : "#f0b90b"
                        radius: 6
                    }
                    contentItem: Text {
                        text: parent.text
                        color: "#000000"
                        font.pixelSize: 11
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: root.close()
                }
            }
        }
    }
}
