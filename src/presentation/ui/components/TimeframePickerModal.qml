import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// TimeframePickerModal — Modal dialog for picking chart/backtest interval timeframe.
ModalDialogCard {
    id: root
    title: "CHỌN KHUNG THỜI GIAN"
    iconSource: "image://icons/clock/accent"
    preferredWidth: 380
    preferredHeight: 240

    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        GridLayout {
            Layout.fillWidth: true
            columns: 4
            columnSpacing: 10
            rowSpacing: 10

            Repeater {
                model: root.hasViewModel ? viewModel.timeframeOptions : ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]

                Button {
                    id: tfBtn
                    Layout.fillWidth: true
                    implicitHeight: 38
                    required property var modelData
                    required property int index

                    readonly property bool isSelected: root.hasViewModel && modelData === viewModel.selectedTimeframe

                    background: Rectangle {
                        color: tfBtn.isSelected ? "#242738" : (tfBtn.hovered ? "#1b1d28" : "#141620")
                        border.color: tfBtn.isSelected ? (Theme && Theme.accent ? Theme.accent : "#f0b90b") : (Theme && Theme.border ? Theme.border : "#2a2d3e")
                        border.width: tfBtn.isSelected ? 1.5 : 1
                        radius: 8
                    }

                    contentItem: Text {
                        text: tfBtn.modelData
                        color: tfBtn.isSelected ? (Theme && Theme.accent ? Theme.accent : "#f0b90b") : (Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb")
                        font.pixelSize: 12
                        font.bold: tfBtn.isSelected
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    onClicked: {
                        if (root.hasViewModel) {
                            viewModel.selectedTimeframe = modelData
                        }
                        root.close()
                    }
                }
            }
        }
    }
}
