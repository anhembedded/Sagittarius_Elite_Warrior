import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0
import "../../components"

Rectangle {
    id: root
    implicitWidth: 1200
    implicitHeight: 120
    color: Theme.bg

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 10

        // ================= ROW 1: TOOLBAR =================
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            // 1. Strategy ComboBox — real StrategyRegistry keys (BOT-026),
            // not a mockup list. Category/description are blank until a
            // registry entry actually has them (BOT-046/BOT-047).
            StrategyComboBox {
                id: strategyCombo
                objectName: "cboBacktestStrategy"
                model: viewModel.strategyOptions
                enabled: viewModel.controlsEnabled
                Layout.preferredWidth: 320

                property bool _initialized: false
                Component.onCompleted: {
                    _syncFromViewModel()
                    _initialized = true
                }
                Connections {
                    target: viewModel
                    function onSelectedStrategyKeyChanged() { strategyCombo._syncFromViewModel() }
                }
                function _syncFromViewModel() {
                    for (var i = 0; i < model.length; ++i) {
                        if (model[i].key === viewModel.selectedStrategyKey) {
                            currentIndex = i
                            return
                        }
                    }
                }
                onActivated: (index) => {
                    if (_initialized) viewModel.selectedStrategyKey = model[index].key
                }
            }

            // 2. Timeframe
            ComboBox {
                id: timeframeCombo
                objectName: "cboBacktestTimeframe"
                implicitHeight: 32
                implicitWidth: 100
                model: viewModel.timeframeOptions
                enabled: viewModel.controlsEnabled
                background: Rectangle { color: "transparent"; border.color: Theme.border; radius: 4 }
                contentItem: Text {
                    leftPadding: 8
                    text: timeframeCombo.displayText
                    color: Theme.textPrimary
                    font.pixelSize: 11
                    verticalAlignment: Text.AlignVCenter
                }

                property bool _initialized: false
                Component.onCompleted: {
                    var idx = model.indexOf(viewModel.selectedTimeframe)
                    if (idx >= 0) currentIndex = idx
                    _initialized = true
                }
                onActivated: (index) => {
                    if (_initialized) viewModel.selectedTimeframe = model[index]
                }
            }

            // 3. Time range preset
            ComboBox {
                id: rangeCombo
                objectName: "cboBacktestRange"
                implicitHeight: 32
                implicitWidth: 140
                model: viewModel.timeRangePresetOptions
                textRole: "label"
                enabled: viewModel.controlsEnabled
                background: Rectangle { color: "transparent"; border.color: Theme.border; radius: 4 }
                contentItem: Text {
                    leftPadding: 8
                    text: rangeCombo.displayText
                    color: Theme.textPrimary
                    font.pixelSize: 11
                    verticalAlignment: Text.AlignVCenter
                }

                property bool _initialized: false
                Component.onCompleted: {
                    for (var i = 0; i < model.length; ++i) {
                        if (model[i].value === viewModel.timeRangePreset) {
                            currentIndex = i
                            break
                        }
                    }
                    _initialized = true
                }
                onActivated: (index) => {
                    if (_initialized) viewModel.timeRangePreset = model[index].value
                }
            }

            // 3b. Custom range fields — only relevant when preset === "custom"
            RowLayout {
                spacing: 6
                visible: viewModel.timeRangePreset === "custom"

                DateTimePicker {
                    objectName: "txtBacktestRangeStart"
                    implicitWidth: 150
                    text: viewModel.customStartText
                    enabled: viewModel.controlsEnabled
                    placeholderText: "From  yyyy-MM-dd HH:mm"
                    onTextEdited: (text) => viewModel.customStartText = text
                }
                DateTimePicker {
                    objectName: "txtBacktestRangeEnd"
                    implicitWidth: 150
                    text: viewModel.customEndText
                    enabled: viewModel.controlsEnabled
                    placeholderText: "To  yyyy-MM-dd HH:mm"
                    onTextEdited: (text) => viewModel.customEndText = text
                }
            }

            // 4. Capital
            TextField {
                id: capitalField
                objectName: "txtBacktestCapital"
                implicitWidth: 100
                implicitHeight: 32
                text: viewModel.initialCapitalText
                enabled: viewModel.controlsEnabled
                color: Theme.textPrimary
                font.pixelSize: 11
                horizontalAlignment: TextInput.AlignRight
                background: FieldBackground {}
                validator: DoubleValidator { bottom: 0 }
                onEditingFinished: viewModel.initialCapitalText = text
            }

            // 5. Order Execution
            Button {
                implicitHeight: 32; background: Rectangle { color: "#25262B"; border.color: Theme.border; radius: 4 }
                onClicked: orderExecMenu.open()
                contentItem: RowLayout {
                    spacing: 6
                    Image { source: "image://icons/briefcase/accent"; sourceSize: Qt.size(14, 14) }
                    Text { text: "Thực thi tập lệnh"; color: Theme.textPrimary; font.pixelSize: 11; font.bold: true }
                    Image { source: "image://icons/chevron-down/muted"; sourceSize: Qt.size(12, 12) }
                }
            }

            Item { Layout.fillWidth: true }

            // Action Buttons
            Button {
                objectName: "btnBacktestBotParams"
                text: "Thông số Bot"
                implicitHeight: 32
                // Disabled for BOT-022 — enabled once BOT-047 (dynamic params
                // form) exists to actually read/write something real here.
                enabled: false
                background: Rectangle { color: "transparent" }
                contentItem: Text { text: parent.text; color: Theme.muted; font.pixelSize: 12; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                onClicked: {
                    botParamsDialog.strategyIndex = strategyCombo.currentIndex
                    botParamsDialog.strategyName = strategyCombo.currentText
                    botParamsDialog.open()
                }
            }

            Button {
                objectName: "btnRunBacktest"
                text: "Chạy Backtest"
                implicitWidth: 140
                implicitHeight: 32
                enabled: viewModel.controlsEnabled
                background: Rectangle { color: enabled ? Theme.accent : Theme.border; radius: 4 }
                contentItem: RowLayout {
                    spacing: 6; anchors.centerIn: parent
                    Image { source: "image://icons/play/black"; sourceSize: Qt.size(14, 14) }
                    Text { text: "Chạy Backtest"; color: "#000000"; font.pixelSize: 12; font.bold: true }
                }
                onClicked: viewModel.requestRun()
            }
        }

        // ================= ROW 2: RESULT (raw text — BOT-022) =================
        // Temporary raw display so the config -> dispatch -> BacktestResult ->
        // screen path can be verified end-to-end. Replaced by proper
        // Performance Summary / Chart / Trade Logs panels in BOT-055/056/057.
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            TextArea {
                objectName: "txtBacktestResult"
                text: viewModel.resultText
                readOnly: true
                wrapMode: TextArea.Wrap
                color: viewModel.resultIsError ? "#ff5252" : Theme.textPrimary
                font.pixelSize: 11
                font.family: "monospace"
                background: Rectangle { color: "transparent" }
            }
        }
    }

    BotParamsDialog {
        id: botParamsDialog
    }

    OrderExecutionMenu {
        id: orderExecMenu
        x: 650 // Approx pos based on design, can be anchored dynamically if needed
        y: 60
    }
}
