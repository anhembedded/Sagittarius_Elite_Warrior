import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0
import "../../components"

Item {
    id: root
    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

    readonly property bool hasOpenModal: (botParamsDialog !== null && botParamsDialog.visible)
                                       || (extendedMetricsPopup !== null && extendedMetricsPopup.visible)
                                       || (limitationsPopup !== null && limitationsPopup.visible)
                                       || (capitalPopup !== null && capitalPopup.visible)
                                       || (indicatorPickerMenu !== null && indicatorPickerMenu.visible)
                                       || (orderExecMenu !== null && orderExecMenu.visible)

    Connections {
        target: !root.hasViewModel ? null : viewModel

        function onOpenBotParamsRequested(strategyName) {
            botParamsDialog.strategyName = strategyName
            botParamsDialog.open()
        }

        function onOpenExtendedMetricsRequested() {
            extendedMetricsPopup.open()
        }

        function onOpenLimitationsRequested() {
            limitationsPopup.open()
        }

        function onOpenCapitalRequested(x, y) {
            capitalPopup.x = x
            capitalPopup.y = y
            capitalInput.text = root.hasViewModel ? viewModel.initialCapitalText : ""
            var idx = root.hasViewModel ? viewModel.currencyOptions.indexOf(viewModel.selectedCurrency) : -1
            if (idx >= 0) currencyCombo.currentIndex = idx
            capitalPopup.open()
        }

        function onOpenIndicatorPickerRequested(x, y) {
            indicatorPickerMenu.x = x
            indicatorPickerMenu.y = y
            indicatorPickerMenu.open()
        }

        function onOpenOrderExecutionRequested(x, y) {
            orderExecMenu.x = x
            orderExecMenu.y = y
            orderExecMenu.open()
        }
    }

    // 1. Capital Popup
    Popup {
        id: capitalPopup
        width: 280
        modal: true
        dim: false
        z: 9999
        padding: 16

        background: Rectangle {
            color: "#161822"
            border.color: "#2a2d3e"
            border.width: 1
            radius: 8
        }

        ColumnLayout {
            width: parent.width
            spacing: 12

            Text {
                text: "Thiết lập vốn ban đầu"
                color: Theme.textPrimary
                font.pixelSize: 13
                font.bold: true
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                TextField {
                    id: capitalInput
                    objectName: "txtBacktestCapital"
                    Layout.fillWidth: true
                    implicitHeight: 34
                    text: root.hasViewModel ? viewModel.initialCapitalText : ""
                    color: Theme.textPrimary
                    font.pixelSize: 12
                    font.bold: true
                    background: Rectangle {
                        color: "#10121a"
                        border.color: "#2a2d3e"
                        radius: 6
                    }
                    validator: DoubleValidator { bottom: 0 }
                }

                ComboBox {
                    id: currencyCombo
                    objectName: "cboBacktestCurrency"
                    implicitWidth: 85
                    implicitHeight: 34
                    model: root.hasViewModel ? viewModel.currencyOptions : []
                    background: Rectangle {
                        color: "#202330"
                        border.color: "#2a2d3e"
                        radius: 6
                    }
                    contentItem: Text {
                        leftPadding: 8
                        text: currencyCombo.displayText
                        color: Theme.textPrimary
                        font.pixelSize: 11
                        font.bold: true
                        verticalAlignment: Text.AlignVCenter
                    }
                    Component.onCompleted: {
                        var idx = root.hasViewModel ? model.indexOf(viewModel.selectedCurrency) : -1
                        if (idx >= 0) currentIndex = idx
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Item { Layout.fillWidth: true }

                Button {
                    text: "Hủy"
                    implicitWidth: 65
                    implicitHeight: 30
                    background: Rectangle {
                        color: "#242738"
                        radius: 6
                    }
                    contentItem: Text {
                        text: parent.text
                        color: Theme.muted
                        font.pixelSize: 11
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: capitalPopup.close()
                }

                Button {
                    text: "Áp dụng"
                    implicitWidth: 85
                    implicitHeight: 30
                    background: Rectangle {
                        color: Theme.accent
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
                    onClicked: {
                        if (root.hasViewModel) {
                            viewModel.initialCapitalText = capitalInput.text
                            viewModel.selectedCurrency = currencyCombo.currentText
                        }
                        capitalPopup.close()
                    }
                }
            }
        }
    }

    // 2. Extended Metrics Popup
    Popup {
        id: extendedMetricsPopup
        objectName: "extendedMetricsPopup"
        width: 440
        modal: true
        dim: true
        anchors.centerIn: Overlay.overlay
        padding: 18

        background: Rectangle {
            color: "#141620"
            border.color: "#282c3f"
            border.width: 1
            radius: 10
        }

        ColumnLayout {
            width: parent.width
            spacing: 14

            RowLayout {
                spacing: 8
                Image { source: "image://icons/info/accent"; sourceSize: Qt.size(16, 16) }
                Text {
                    text: "CHỈ SỐ CHI TIẾT BACKTEST"
                    color: Theme.textPrimary
                    font.pixelSize: 12
                    font.bold: true
                    font.letterSpacing: 1
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 12
                rowSpacing: 12

                Repeater {
                    model: root.hasViewModel ? viewModel.extendedStatCards : []
                    delegate: MetricCard {
                        objectName: "cardExtendedMetric_" + index
                        Layout.fillWidth: true
                        title: modelData.title
                        value: modelData.value
                        suffix: modelData.suffix
                    }
                }
            }
        }
    }

    // 3. Limitations Popup
    Popup {
        id: limitationsPopup
        objectName: "limitationsPopup"
        width: 440
        modal: true
        dim: true
        anchors.centerIn: Overlay.overlay
        padding: 18

        background: Rectangle {
            color: "#141620"
            border.color: "#282c3f"
            border.width: 1
            radius: 10
        }

        ColumnLayout {
            width: parent.width
            spacing: 14

            RowLayout {
                spacing: 8
                Image { source: "image://icons/info/accent"; sourceSize: Qt.size(16, 16) }
                Text {
                    text: "GIỚI HẠN CỦA LẦN CHẠY NÀY"
                    color: Theme.textPrimary
                    font.pixelSize: 12
                    font.bold: true
                    font.letterSpacing: 1
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8

                Repeater {
                    model: root.hasViewModel ? viewModel.limitations : []
                    delegate: RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            text: "•"
                            color: Theme.muted
                            font.pixelSize: 12
                            Layout.alignment: Qt.AlignTop
                        }
                        Text {
                            objectName: "lblLimitation_" + index
                            Layout.fillWidth: true
                            text: modelData
                            color: Theme.textPrimary
                            font.pixelSize: 11
                            wrapMode: Text.Wrap
                        }
                    }
                }
            }
        }
    }

    // 4. Bot Params Dialog
    BotParamsDialog {
        id: botParamsDialog
    }

    // 5. Indicator Picker Menu
    IndicatorPickerMenu {
        id: indicatorPickerMenu
    }

    // 6. Order Execution Menu
    OrderExecutionMenu {
        id: orderExecMenu
    }
}
