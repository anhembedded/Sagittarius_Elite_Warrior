import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// SymbolPickerModal (BOT-102) — Modal dialog for picking the Backtest
// symbol. Unlike TimeframePickerModal/StrategyPickerModal (local, always
// populated), symbolOptions is fetched from the exchange lazily and may be
// empty either because the fetch hasn't finished yet or because it failed
// — this modal shows a loading state for both, it has no way to tell them
// apart (a persistent error is visible in the Backtest log panel instead).
ModalDialogCard {
    id: root
    title: "CHỌN SYMBOL"
    iconSource: "image://icons/dollar-sign/accent"
    preferredWidth: 420
    preferredHeight: 320

    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null
    readonly property bool hasOptions: root.hasViewModel && viewModel.symbolOptions.length > 0

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        TextField {
            id: searchField
            objectName: "txtSymbolSearch"
            Layout.fillWidth: true
            placeholderText: "Tìm symbol (vd: BTC)"
            visible: root.hasOptions
        }

        Text {
            visible: !root.hasOptions
            Layout.fillWidth: true
            Layout.fillHeight: true
            text: "Đang tải danh sách symbol từ sàn..."
            color: Theme && Theme.textMuted ? Theme.textMuted : "#8b8fa3"
            font.pixelSize: 12
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.hasOptions
            clip: true

            GridLayout {
                width: parent.width
                columns: 3
                columnSpacing: 8
                rowSpacing: 8

                Repeater {
                    model: root.hasOptions
                        ? viewModel.symbolOptions.filter(function (s) {
                            return searchField.text === "" || s.indexOf(searchField.text.toUpperCase()) !== -1
                        })
                        : []

                    Button {
                        id: symBtn
                        Layout.fillWidth: true
                        implicitHeight: 36
                        required property var modelData
                        required property int index

                        readonly property bool isSelected: root.hasViewModel && modelData === viewModel.selectedSymbol

                        background: Rectangle {
                            color: symBtn.isSelected ? "#242738" : (symBtn.hovered ? "#1b1d28" : "#141620")
                            border.color: symBtn.isSelected ? (Theme && Theme.accent ? Theme.accent : "#f0b90b") : (Theme && Theme.border ? Theme.border : "#2a2d3e")
                            border.width: symBtn.isSelected ? 1.5 : 1
                            radius: 8
                        }

                        contentItem: Text {
                            text: symBtn.modelData
                            color: symBtn.isSelected ? (Theme && Theme.accent ? Theme.accent : "#f0b90b") : (Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb")
                            font.pixelSize: 11
                            font.bold: symBtn.isSelected
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: {
                            if (root.hasViewModel) {
                                viewModel.selectedSymbol = modelData
                            }
                            root.close()
                        }
                    }
                }
            }
        }
    }
}
