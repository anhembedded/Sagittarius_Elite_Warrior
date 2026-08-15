import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0
import "../../components"

Rectangle {
    id: root
    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null
    // BOT-089: height is no longer a hardcoded 200 — that number had
    // already been bumped once before (120 -> 190 in backtest_view.py, for
    // the same reason: BOT-055's stat cards no longer fit) and would keep
    // needing bumping every time a row is added. `contentColumn`'s own
    // implicit height (the real sum of its rows) drives this instead;
    // BackTestView._bind_top_panel_height() reads it back and resizes the
    // QQuickWidget to match (SizeRootObjectToView ignores this property
    // otherwise).
    //
    // Width stays as-is (not content-driven): every row here uses
    // Layout.fillWidth, so none reports a meaningful implicit width to sum
    // — width is meant to stretch to whatever the container gives it, not
    // shrink to content. That's also why implicitWidth was never the real
    // cause of the toolbar clipping in BUG-004: the default QQuickWidget
    // resize mode (SizeRootObjectToView) ignores implicitWidth entirely and
    // always matches the widget's actual width. The real fix for
    // "narrower than the toolbar needs" is the ScrollView added below.
    property int panelMargin: 12
    implicitHeight: contentColumn.implicitHeight + panelMargin * 2
    color: "#0d0e14"

    ColumnLayout {
        id: contentColumn
        objectName: "contentColumn"
        anchors.fill: parent
        anchors.margins: root.panelMargin
        spacing: 12

        // ================= ROW 1: TOOLBAR & CONTROLS =================
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 52
            color: "#12141d"
            border.color: "#222533"
            border.width: 1
            radius: 8
            clip: true

            // BOT-089 §2.2: a narrow window used to clip the trailing
            // controls (e.g. "CHẠY BACKTEST") off the right edge with no
            // way to reach them — silent overflow. A horizontal scroll is
            // the minimal fix that guarantees every control stays reachable
            // regardless of window width, without changing the toolbar's
            // layout/spacing for the common (wide enough) case.
            ScrollView {
                id: toolbarScroll
                objectName: "toolbarScroll"
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                clip: true
                // BOT-089: verified against the Basic style's actual
                // ScrollBar.qml — its handle is `opacity: 0.0` by default
                // and only reaches 0.75 in the "active" state, which
                // requires `policy === AlwaysOn` OR the bar currently being
                // hovered/dragged. `AsNeeded` alone (the usual choice)
                // therefore renders NOTHING until the user happens to
                // hover exactly over the (invisible) bar — a discoverable
                // affordance is the whole point here (BUG-004: "CHẠY
                // BACKTEST" going unreachable with no visible sign it's
                // still there), so this toggles the policy itself between
                // AlwaysOn (only when content truly overflows) and
                // AlwaysOff, rather than trying to force `visible`/opacity
                // on top of AsNeeded's built-in hover gating.
                ScrollBar.horizontal.policy: toolbarRow.implicitWidth > toolbarScroll.width
                    ? ScrollBar.AlwaysOn
                    : ScrollBar.AlwaysOff
                ScrollBar.vertical.policy: ScrollBar.AlwaysOff

                RowLayout {
                    id: toolbarRow
                    objectName: "toolbarRow"
                    height: toolbarScroll.height
                    spacing: 10

                    // 1. Strategy ComboBox
                    StrategyComboBox {
                        id: strategyCombo
                        objectName: "cboBacktestStrategy"
                        model: root.hasViewModel ? viewModel.strategyOptions : []
                        enabled: root.hasViewModel && viewModel.controlsEnabled
                        Layout.preferredWidth: 300

                        property bool _initialized: false
                        Component.onCompleted: {
                            _syncFromViewModel()
                            _initialized = true
                        }
                        Connections {
                            target: !root.hasViewModel ? null : viewModel
                            function onSelectedStrategyKeyChanged() { strategyCombo._syncFromViewModel() }
                        }
                        function _syncFromViewModel() {
                            for (var i = 0; i < model.length; ++i) {
                                if (root.hasViewModel && model[i].key === viewModel.selectedStrategyKey) {
                                    currentIndex = i
                                    return
                                }
                            }
                        }
                        onActivated: (index) => {
                            if (_initialized && root.hasViewModel) viewModel.selectedStrategyKey = model[index].key
                        }
                    }

                    // 2. Timeframe
                    ComboBox {
                        id: timeframeCombo
                        objectName: "cboBacktestTimeframe"
                        implicitHeight: 34
                        implicitWidth: 95
                        model: root.hasViewModel ? viewModel.timeframeOptions : []
                        enabled: root.hasViewModel && viewModel.controlsEnabled
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
                            var idx = root.hasViewModel ? model.indexOf(viewModel.selectedTimeframe) : -1
                            if (idx >= 0) currentIndex = idx
                            _initialized = true
                        }
                        onActivated: (index) => {
                            if (_initialized && root.hasViewModel) viewModel.selectedTimeframe = model[index]
                        }
                    }

                    // 3. Time range preset
                    ComboBox {
                        id: rangeCombo
                        objectName: "cboBacktestRange"
                        implicitHeight: 34
                        implicitWidth: 135
                        model: root.hasViewModel ? viewModel.timeRangePresetOptions : []
                        textRole: "label"
                        enabled: root.hasViewModel && viewModel.controlsEnabled
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
                                if (root.hasViewModel && model[i].value === viewModel.timeRangePreset) {
                                    currentIndex = i
                                    break
                                }
                            }
                            _initialized = true
                        }
                        onActivated: (index) => {
                            if (_initialized && root.hasViewModel) viewModel.timeRangePreset = model[index].value
                        }
                    }

                    // 3b. Custom range fields
                    RowLayout {
                        spacing: 6
                        visible: root.hasViewModel && viewModel.timeRangePreset === "custom"

                        DateTimePicker {
                            objectName: "txtBacktestRangeStart"
                            implicitWidth: 145
                            text: root.hasViewModel ? viewModel.customStartText : ""
                            enabled: root.hasViewModel && viewModel.controlsEnabled
                            placeholderText: "Từ yyyy-MM-dd HH:mm"
                            onTextEdited: (text) => { if (root.hasViewModel) viewModel.customStartText = text }
                        }
                        DateTimePicker {
                            objectName: "txtBacktestRangeEnd"
                            implicitWidth: 145
                            text: root.hasViewModel ? viewModel.customEndText : ""
                            enabled: root.hasViewModel && viewModel.controlsEnabled
                            placeholderText: "Đến yyyy-MM-dd HH:mm"
                            onTextEdited: (text) => { if (root.hasViewModel) viewModel.customEndText = text }
                        }
                    }

                    // 4. Capital Dropdown Button
                    Button {
                        id: btnCapital
                        objectName: "btnBacktestCapital"
                        implicitHeight: 34
                        enabled: root.hasViewModel && viewModel.controlsEnabled
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
                                text: root._formatCapitalDisplay(
                                    root.hasViewModel ? viewModel.initialCapitalText : "",
                                    root.hasViewModel ? viewModel.selectedCurrency : ""
                                )
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
                        enabled: root.hasViewModel && viewModel.controlsEnabled
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
                        id: runBtnRoot
                        objectName: "btnRunBacktest"
                        implicitWidth: 145
                        implicitHeight: 34
                        enabled: root.hasViewModel && viewModel.controlsEnabled
                        onClicked: { if (root.hasViewModel) viewModel.requestRun() }
                        background: Rectangle {
                            id: runBtnBg
                            color: enabled ? (runBtnRoot.hovered ? "#12e680" : "#10b981") : "#242736"
                            radius: 6
                            Behavior on color { ColorAnimation { duration: 150 } }
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
        }

        // ================= HEADER: PERFORMANCE METRICS =================
        RowLayout {
            Layout.fillWidth: true
            visible: root.hasViewModel && viewModel.primaryStatCards.length > 0
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

                Button {
                    // BOT-081: "kín đáo nhưng tìm thấy được" — unlike
                    // resultWarningText (must stay visible, never behind a
                    // click), the limitation disclosure is fine tucked
                    // behind an icon; the task explicitly warns against
                    // turning it into another always-visible banner ("cám
                    // dỗ làm quá tay" -> alarm fatigue). A Button (not
                    // Rectangle+MouseArea) so it stays clickable from
                    // Python tests — BOT-057/BOT-083's convention.
                    objectName: "btnBacktestLimitations"
                    implicitWidth: 18
                    implicitHeight: 18
                    padding: 0
                    background: Rectangle { color: "transparent" }
                    contentItem: Image {
                        source: "image://icons/info/muted"
                        sourceSize: Qt.size(13, 13)
                        anchors.centerIn: parent
                    }
                    onClicked: limitationsPopup.open()
                }
            }

            Text {
                // BOT-079 follow-up: an earlier version squeezed this into
                // the Net PnL MetricCard badge (a small fixed pill) and
                // overflowed it. This header row has real width to spare —
                // reusing its existing fillWidth spacer costs 0 extra
                // vertical space in BackTestTopPanel's fixed-height budget
                // (backtest_view.py's _TOP_PANEL_HEIGHT), and elide only
                // trims an unusually long combined message, it doesn't hide
                // the warning behind a click.
                objectName: "lblResultWarning"
                Layout.fillWidth: true
                visible: root.hasViewModel && text !== ""
                text: root.hasViewModel ? viewModel.resultWarningText : ""
                color: "#ef5350"
                font.pixelSize: 11
                font.bold: true
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignRight
            }

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
        // BOT-089: this row used to be `Layout.fillHeight: true` — free to
        // do in a fixed-height panel with room to spare, but a
        // content-driven panel has none: a fillHeight item reports 0 to its
        // parent's implicit-size computation (fillHeight only distributes
        // space that's already been decided; it isn't itself a size
        // request), so contentColumn's implicitHeight silently ignored
        // this entire row and both the stat cards AND the result-text box
        // rendered clipped. Now sized explicitly from whichever of the two
        // states is actually visible.
        Item {
            Layout.fillWidth: true
            implicitHeight: root.hasViewModel && viewModel.primaryStatCards.length > 0
                ? statCardsRow.implicitHeight
                : resultColumn.implicitHeight
            Layout.preferredHeight: implicitHeight

            RowLayout {
                id: statCardsRow
                anchors.fill: parent
                visible: root.hasViewModel && viewModel.primaryStatCards.length > 0
                spacing: 12

                Repeater {
                    model: root.hasViewModel ? viewModel.primaryStatCards : []

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
                id: resultColumn
                anchors.fill: parent
                visible: !root.hasViewModel || viewModel.primaryStatCards.length === 0
                spacing: 8

                ScrollView {
                    // Unlike the stat cards (sized from MetricCard's own
                    // implicitHeight), raw result text has no natural
                    // content height worth measuring — it's a scrollable
                    // viewport by design. A fixed budget here is a
                    // deliberate UI choice (how big should the text box
                    // be), not the "container ignoring what content needs"
                    // class of bug this task exists to fix.
                    Layout.fillWidth: true
                    Layout.preferredHeight: 120
                    clip: true

                    TextArea {
                        objectName: "txtBacktestResult"
                        text: root.hasViewModel ? viewModel.resultText : ""
                        readOnly: true
                        wrapMode: TextArea.Wrap
                        color: root.hasViewModel && viewModel.resultIsError ? "#ff5252" : Theme.textPrimary
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
                    visible: root.hasViewModel && viewModel.needsDataSync
                    enabled: root.hasViewModel && viewModel.uiMode !== "SYNCING"
                    implicitHeight: 34
                    text: root.hasViewModel
                        ? (viewModel.uiMode === "SYNCING" ? "Đang đồng bộ..." : "Đồng bộ dữ liệu ngay")
                        : "Đồng bộ dữ liệu ngay"
                    background: Rectangle { color: enabled ? Theme.accent : "#282b3a"; radius: 6 }
                    contentItem: Text {
                        text: parent.text
                        color: "#000000"
                        font.pixelSize: 12
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: { if (root.hasViewModel) viewModel.requestSync() }
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
        capitalInput.text = root.hasViewModel ? viewModel.initialCapitalText : ""
        var idx = root.hasViewModel ? viewModel.currencyOptions.indexOf(viewModel.selectedCurrency) : -1
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

    Popup {
        id: limitationsPopup
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

