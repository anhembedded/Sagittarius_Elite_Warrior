import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0
import "../../components"

Rectangle {
    id: root
    implicitWidth: 1200
    implicitHeight: 200
    color: "#0d0e14"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        // ================= ROW 1: TOOLBAR & CONTROLS =================
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 52
            color: "#12141d"
            border.color: "#222533"
            border.width: 1
            radius: 8

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 10

                // 1. Strategy ComboBox
                StrategyComboBox {
                    id: strategyCombo
                    objectName: "cboBacktestStrategy"
                    model: viewModel.strategyOptions
                    enabled: viewModel.controlsEnabled
                    Layout.preferredWidth: 300

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
                    implicitHeight: 34
                    implicitWidth: 95
                    model: viewModel.timeframeOptions
                    enabled: viewModel.controlsEnabled
                    background: Rectangle {
                        color: "#181a24"
                        border.color: "#2a2d3d"
                        border.width: 1
                        radius: 6
                    }
                    contentItem: Text {
                        leftPadding: 10
                        text: timeframeCombo.displayText
                        color: Theme.textPrimary
                        font.pixelSize: 11
                        font.bold: true
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
                    implicitHeight: 34
                    implicitWidth: 135
                    model: viewModel.timeRangePresetOptions
                    textRole: "label"
                    enabled: viewModel.controlsEnabled
                    background: Rectangle {
                        color: "#181a24"
                        border.color: "#2a2d3d"
                        border.width: 1
                        radius: 6
                    }
                    contentItem: Text {
                        leftPadding: 10
                        text: rangeCombo.displayText
                        color: Theme.textPrimary
                        font.pixelSize: 11
                        font.bold: true
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

                // 3b. Custom range fields
                RowLayout {
                    spacing: 6
                    visible: viewModel.timeRangePreset === "custom"

                    DateTimePicker {
                        objectName: "txtBacktestRangeStart"
                        implicitWidth: 145
                        text: viewModel.customStartText
                        enabled: viewModel.controlsEnabled
                        placeholderText: "Từ yyyy-MM-dd HH:mm"
                        onTextEdited: (text) => viewModel.customStartText = text
                    }
                    DateTimePicker {
                        objectName: "txtBacktestRangeEnd"
                        implicitWidth: 145
                        text: viewModel.customEndText
                        enabled: viewModel.controlsEnabled
                        placeholderText: "Đến yyyy-MM-dd HH:mm"
                        onTextEdited: (text) => viewModel.customEndText = text
                    }
                }

                // 4. Capital Dropdown Button
                Button {
                    id: btnCapital
                    objectName: "btnBacktestCapital"
                    implicitHeight: 34
                    enabled: viewModel.controlsEnabled
                    background: Rectangle {
                        color: "#181a24"
                        border.color: "#2a2d3d"
                        border.width: 1
                        radius: 6
                    }
                    contentItem: RowLayout {
                        spacing: 6
                        anchors.centerIn: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10

                        Image {
                            source: "image://icons/dollar-sign/success"
                            sourceSize: Qt.size(13, 13)
                        }

                        Text {
                            text: root._formatCapitalDisplay(viewModel.initialCapitalText, viewModel.selectedCurrency)
                            color: Theme.textPrimary
                            font.pixelSize: 11
                            font.bold: true
                            verticalAlignment: Text.AlignVCenter
                        }

                        Image {
                            source: "image://icons/chevron-down/muted"
                            sourceSize: Qt.size(11, 11)
                        }
                    }
                    onClicked: root.openCapitalPopup()
                }

                // 5. Order Execution
                Button {
                    implicitHeight: 34
                    background: Rectangle { color: "#181a24"; border.color: "#2a2d3d"; border.width: 1; radius: 6 }
                    onClicked: orderExecMenu.open()
                    contentItem: RowLayout {
                        spacing: 6
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        Image { source: "image://icons/briefcase/accent"; sourceSize: Qt.size(13, 13) }
                        Text { text: "Tập lệnh"; color: Theme.textPrimary; font.pixelSize: 11; font.bold: true }
                        Image { source: "image://icons/chevron-down/muted"; sourceSize: Qt.size(11, 11) }
                    }
                }

                // 6. Indicator picker (BOT-064)
                Button {
                    objectName: "btnBacktestIndicatorPicker"
                    implicitHeight: 34
                    background: Rectangle { color: "#181a24"; border.color: "#2a2d3d"; border.width: 1; radius: 6 }
                    onClicked: indicatorPickerMenu.open()
                    contentItem: RowLayout {
                        spacing: 6
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        Image { source: "image://icons/sliders/accent"; sourceSize: Qt.size(13, 13) }
                        Text { text: "Chỉ báo"; color: Theme.textPrimary; font.pixelSize: 11; font.bold: true }
                        Image { source: "image://icons/chevron-down/muted"; sourceSize: Qt.size(11, 11) }
                    }
                }

                Item { Layout.fillWidth: true }

                // Action Buttons
                Button {
                    objectName: "btnBacktestBotParams"
                    text: "Thông số Bot"
                    implicitHeight: 34
                    enabled: viewModel.controlsEnabled
                    background: Rectangle {
                        color: "#1c1e2b"
                        border.color: "#2d3145"
                        border.width: 1
                        radius: 6
                    }
                    contentItem: RowLayout {
                        spacing: 6
                        anchors.centerIn: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        Image { source: "image://icons/settings/accent"; sourceSize: Qt.size(13, 13) }
                        Text { text: "Thông số Bot"; color: Theme.textPrimary; font.pixelSize: 11; font.bold: true }
                    }
                    onClicked: {
                        botParamsDialog.strategyName = strategyCombo.currentText
                        botParamsDialog.open()
                    }
                }

                Button {
                    objectName: "btnRunBacktest"
                    implicitWidth: 145
                    implicitHeight: 34
                    enabled: viewModel.controlsEnabled
                    background: Rectangle {
                        id: runBtnBg
                        color: enabled ? (runBtnMouse.containsMouse ? "#12e680" : "#10b981") : "#242736"
                        radius: 6
                        Behavior on color { ColorAnimation { duration: 150 } }
                    }
                    MouseArea {
                        id: runBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: viewModel.requestRun()
                    }
                    contentItem: RowLayout {
                        spacing: 8
                        anchors.centerIn: parent
                        Image { source: "image://icons/play/black"; sourceSize: Qt.size(13, 13) }
                        Text { text: "CHẠY BACKTEST"; color: "#08090d"; font.pixelSize: 11; font.bold: true; font.letterSpacing: 0.5 }
                    }
                }
            }
        }

        // ================= HEADER: PERFORMANCE METRICS =================
        RowLayout {
            Layout.fillWidth: true
            visible: viewModel.primaryStatCards.length > 0
            spacing: 10

            RowLayout {
                spacing: 8
                Rectangle {
                    width: 3
                    height: 14
                    color: Theme.accent
                    radius: 2
                }
                Text {
                    text: "CHỈ SỐ HIỆU SUẤT BACKTEST"
                    color: Theme.textPrimary
                    font.pixelSize: 12
                    font.bold: true
                    font.letterSpacing: 0.8
                }
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
                        font.bold: true
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

        // ================= ROW 2: RESULT METRIC CARDS / STATUS =================
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            RowLayout {
                anchors.fill: parent
                visible: viewModel.primaryStatCards.length > 0
                spacing: 12

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
                spacing: 8

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
                        font.family: "JetBrains Mono, Fira Code, monospace"
                        background: Rectangle {
                            color: "#12141d"
                            border.color: "#222533"
                            border.width: 1
                            radius: 6
                        }
                    }
                }

                Button {
                    objectName: "btnRequestSync"
                    Layout.alignment: Qt.AlignLeft
                    visible: viewModel.needsDataSync
                    enabled: viewModel.uiMode !== "SYNCING"
                    implicitHeight: 34
                    text: viewModel.uiMode === "SYNCING" ? "Đang đồng bộ..." : "Đồng bộ dữ liệu ngay"
                    background: Rectangle { color: enabled ? Theme.accent : "#282b3a"; radius: 6 }
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

    function _formatCapitalDisplay(rawText, currency) {
        return (rawText || "0") + " " + currency
    }

    function openCapitalPopup() {
        var pos = btnCapital.mapToItem(Overlay.overlay, 0, btnCapital.height + 4)
        capitalPopup.x = pos.x
        capitalPopup.y = pos.y
        capitalInput.text = viewModel.initialCapitalText
        var idx = viewModel.currencyOptions.indexOf(viewModel.selectedCurrency)
        if (idx >= 0) currencyCombo.currentIndex = idx
        capitalPopup.open()
    }

    Popup {
        id: capitalPopup
        width: 280
        modal: true
        dim: false
        parent: Overlay.overlay
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
                    text: viewModel.initialCapitalText
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
                    model: viewModel.currencyOptions
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
                        var idx = model.indexOf(viewModel.selectedCurrency)
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
                        viewModel.initialCapitalText = capitalInput.text
                        viewModel.selectedCurrency = currencyCombo.currentText
                        capitalPopup.close()
                    }
                }
            }
        }
    }

    Popup {
        id: extendedMetricsPopup
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

    IndicatorPickerMenu {
        id: indicatorPickerMenu
        x: 650
        y: 60
    }

    OrderExecutionMenu {
        id: orderExecMenu
        x: 650
        y: 60
    }
}

