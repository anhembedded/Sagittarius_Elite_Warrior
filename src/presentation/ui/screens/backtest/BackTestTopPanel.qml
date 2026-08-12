import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0
import "../../components"

Rectangle {
    id: root
    implicitWidth: 1200
    implicitHeight: 190
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
            Rectangle {
                implicitWidth: 130
                implicitHeight: 32
                color: "#25262B"
                border.color: Theme.border
                radius: 4

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 4

                    Image {
                        source: "image://icons/dollar-sign/success"
                        sourceSize: Qt.size(14, 14)
                        Layout.alignment: Qt.AlignVCenter
                    }

                    TextField {
                        id: capitalField
                        objectName: "txtBacktestCapital"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: viewModel.initialCapitalText
                        enabled: viewModel.controlsEnabled
                        color: Theme.textPrimary
                        font.pixelSize: 11
                        font.bold: true
                        horizontalAlignment: TextInput.AlignLeft
                        background: Rectangle { color: "transparent" }
                        validator: DoubleValidator { bottom: 0 }
                        onEditingFinished: viewModel.initialCapitalText = text
                    }

                    Text {
                        text: "USD"
                        color: Theme.textSecondary
                        font.pixelSize: 10
                        font.bold: true
                        verticalAlignment: Text.AlignVCenter
                    }
                }
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
                // BOT-047: the dialog now renders viewModel.botParamsSchema,
                // which the Presenter keeps in sync with the selected
                // strategy — nothing further to build here before opening.
                enabled: viewModel.controlsEnabled
                background: Rectangle { color: "transparent" }
                contentItem: Text { text: parent.text; color: Theme.muted; font.pixelSize: 12; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                onClicked: {
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

        // ================= HEADER: PERFORMANCE METRICS =================
        // Only shown once there's a real BacktestResult to summarize — BOT-057's
        // Trade Logs Table and BOT-056's Chart Canvas still don't exist, so the
        // status text below is what verifies a run end-to-end before that.
        RowLayout {
            Layout.fillWidth: true
            visible: viewModel.primaryStatCards.length > 0
            spacing: 10

            Text {
                text: "CHỈ SỐ HIỆU SUẤT BACKTEST"
                color: Theme.textPrimary
                font.pixelSize: 13
                font.bold: true
                font.letterSpacing: 1
            }

            Item { Layout.fillWidth: true }

            Item {
                Layout.preferredWidth: expandRow.implicitWidth
                Layout.preferredHeight: expandRow.implicitHeight

                RowLayout {
                    id: expandRow
                    anchors.fill: parent
                    spacing: 4

                    Text {
                        objectName: "lnkExpandMetrics"
                        text: "Mở rộng chỉ số chi tiết"
                        color: Theme.accent
                        font.pixelSize: 11
                    }
                    Image { source: "image://icons/chevron-down/accent"; sourceSize: Qt.size(12, 12) }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: extendedMetricsPopup.open()
                }
            }
        }

        // ================= ROW 2: RESULT =================
        // 4 stat cards once a BacktestResult exists (BOT-055); otherwise the
        // raw status text (loading / no data / error) from BOT-022.
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            RowLayout {
                anchors.fill: parent
                visible: viewModel.primaryStatCards.length > 0
                spacing: 10

                Repeater {
                    model: viewModel.primaryStatCards

                    MetricCard {
                        objectName: "cardMetric_" + index
                        Layout.fillWidth: true
                        title: modelData.title
                        value: modelData.value
                        valueColor: modelData.valueColor !== "" ? modelData.valueColor : Theme.textPrimary
                        suffix: modelData.suffix
                        badgeText: modelData.badgeText
                        badgeBgColor: modelData.badgeColor !== "" ? root._withAlpha(modelData.badgeColor, 0.2) : "transparent"
                        badgeTextColor: modelData.badgeColor !== "" ? modelData.badgeColor : Theme.muted
                    }
                }
            }

            ColumnLayout {
                anchors.fill: parent
                visible: viewModel.primaryStatCards.length === 0
                spacing: 6

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

                // BOT-059: only ever shown after a run comes back "no
                // historical data" — lets the user fix that inline instead
                // of leaving the screen to sync from Dev Board.
                Button {
                    objectName: "btnRequestSync"
                    Layout.alignment: Qt.AlignLeft
                    visible: viewModel.needsDataSync
                    enabled: viewModel.uiMode !== "SYNCING"
                    implicitHeight: 32
                    text: viewModel.uiMode === "SYNCING" ? "Đang đồng bộ..." : "Đồng bộ ngay"
                    background: Rectangle { color: enabled ? Theme.accent : Theme.border; radius: 4 }
                    contentItem: Text {
                        text: parent.text
                        color: "#000000"
                        font.pixelSize: 12
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: viewModel.requestSync()
                }
            }
        }
    }

    function _withAlpha(hex, alpha) {
        var c = Qt.color(hex)
        return Qt.rgba(c.r, c.g, c.b, alpha)
    }

    Popup {
        id: extendedMetricsPopup
        width: 420
        modal: true
        dim: true
        anchors.centerIn: Overlay.overlay
        padding: 15

        background: Rectangle {
            color: Theme.bg
            border.color: Theme.border
            border.width: 1
            radius: 6
        }

        ColumnLayout {
            width: parent.width
            spacing: 10

            Text {
                text: "CHỈ SỐ CHI TIẾT"
                color: Theme.textPrimary
                font.pixelSize: 12
                font.bold: true
                font.letterSpacing: 1
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 10
                rowSpacing: 10

                Repeater {
                    model: viewModel.extendedStatCards

                    MetricCard {
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

    BotParamsDialog {
        id: botParamsDialog
    }

    OrderExecutionMenu {
        id: orderExecMenu
        x: 650 // Approx pos based on design, can be anchored dynamically if needed
        y: 60
    }
}
