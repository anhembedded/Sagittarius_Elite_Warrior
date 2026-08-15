import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

// CapitalDialog (BOT-088) — Modal dialog for configuring initial capital and currency.
ModalDialogCard {
    id: root
    title: "THIẾT LẬP VỐN BAN ĐẦU"
    iconSource: "image://icons/dollar-sign/success"
    width: 360
    height: 190

    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

    function openDialog() {
        capitalInput.text = root.hasViewModel ? viewModel.initialCapitalText : "10000"
        var idx = root.hasViewModel ? viewModel.currencyOptions.indexOf(viewModel.selectedCurrency) : -1
        if (idx >= 0) currencyCombo.currentIndex = idx
        root.open()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            TextField {
                id: capitalInput
                objectName: "txtBacktestCapital"
                Layout.fillWidth: true
                implicitHeight: 34
                text: root.hasViewModel ? viewModel.initialCapitalText : "10000"
                color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                font.pixelSize: 12
                font.bold: true
                background: Rectangle {
                    color: "#10121a"
                    border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                    radius: 6
                }
                validator: DoubleValidator { bottom: 0 }
            }

            ComboBox {
                id: currencyCombo
                objectName: "cboBacktestCurrency"
                implicitWidth: 90
                implicitHeight: 34
                model: root.hasViewModel ? viewModel.currencyOptions : ["USD", "USDT", "VND"]
                background: Rectangle {
                    color: "#202330"
                    border.color: Theme && Theme.border ? Theme.border : "#2a2d3e"
                    radius: 6
                }
                contentItem: Text {
                    leftPadding: 8
                    text: currencyCombo.displayText
                    color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
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
    }

    footerData: [
        Item { Layout.fillWidth: true },

        Button {
            text: "Hủy"
            implicitWidth: 70
            implicitHeight: 32
            background: Rectangle {
                color: parent.hovered ? "#2e3247" : "#242738"
                radius: 6
            }
            contentItem: Text {
                text: parent.text
                color: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
                font.pixelSize: 11
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            onClicked: root.close()
        },

        Button {
            text: "Áp dụng"
            implicitWidth: 90
            implicitHeight: 32
            background: Rectangle {
                color: parent.hovered ? "#ffd033" : (Theme && Theme.accent ? Theme.accent : "#f0b90b")
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
                root.close()
            }
        }
    ]
}
