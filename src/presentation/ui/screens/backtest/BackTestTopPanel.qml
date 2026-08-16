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

                    // 1. Strategy Picker Button
                    Button {
                        id: btnStrategy
                        objectName: "btnBacktestStrategy"
                        implicitHeight: 34
                        implicitWidth: 260
                        enabled: root.hasViewModel && viewModel.controlsEnabled
                        background: Rectangle {
                            color: btnStrategy.hovered ? "#222536" : "#181a24"
                            border.color: Theme && Theme.border ? Theme.border : "#2a2d3d"
                            border.width: 1
                            radius: 6
                        }
                        contentItem: RowLayout {
                            spacing: 8
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10

                            Image {
                                source: "image://icons/briefcase/accent"
                                sourceSize: Qt.size(13, 13)
                            }

                            Text {
                                text: root.hasViewModel ? viewModel.selectedStrategyName : "Chọn chiến lược"
                                color: Theme && Theme.accent ? Theme.accent : "#f0b90b"
                                font.pixelSize: 11
                                font.bold: true
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                                verticalAlignment: Text.AlignVCenter
                            }

                            Image {
                                source: "image://icons/chevron-down/muted"
                                sourceSize: Qt.size(11, 11)
                            }
                        }
                        onClicked: {
                            if (root.hasViewModel) viewModel.requestOpenStrategyPicker()
                        }
                    }

                    // 2. Timeframe Button
                    Button {
                        id: btnTimeframe
                        objectName: "btnBacktestTimeframe"
                        implicitHeight: 34
                        implicitWidth: 70
                        enabled: root.hasViewModel && viewModel.controlsEnabled
                        background: Rectangle {
                            color: btnTimeframe.hovered ? "#222536" : "#181a24"
                            border.color: Theme && Theme.border ? Theme.border : "#2a2d3d"
                            border.width: 1
                            radius: 6
                        }
                        contentItem: RowLayout {
                            spacing: 6
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8

                            Text {
                                text: root.hasViewModel ? viewModel.selectedTimeframe : "1m"
                                color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                font.pixelSize: 11
                                font.bold: true
                                horizontalAlignment: Text.AlignHCenter
                                Layout.fillWidth: true
                                verticalAlignment: Text.AlignVCenter
                            }

                            Image {
                                source: "image://icons/chevron-down/muted"
                                sourceSize: Qt.size(11, 11)
                            }
                        }
                        onClicked: {
                            if (root.hasViewModel) viewModel.requestOpenTimeframePicker()
                        }
                    }

                    // 3. Time range preset Button
                    Button {
                        id: btnRange
                        objectName: "btnBacktestRange"
                        implicitHeight: 34
                        implicitWidth: 140
                        enabled: root.hasViewModel && viewModel.controlsEnabled
                        background: Rectangle {
                            color: btnRange.hovered ? "#222536" : "#181a24"
                            border.color: Theme && Theme.border ? Theme.border : "#2a2d3d"
                            border.width: 1
                            radius: 6
                        }
                        contentItem: RowLayout {
                            spacing: 6
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10

                            Image {
                                source: "image://icons/calendar/accent"
                                sourceSize: Qt.size(13, 13)
                            }

                            Text {
                                text: root.hasViewModel ? viewModel.selectedTimeRangePresetLabel : "Toàn bộ lịch sử"
                                color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                                font.pixelSize: 11
                                font.bold: true
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                                verticalAlignment: Text.AlignVCenter
                            }

                            Image {
                                source: "image://icons/chevron-down/muted"
                                sourceSize: Qt.size(11, 11)
                            }
                        }
                        onClicked: {
                            if (root.hasViewModel) viewModel.requestOpenTimeRangePicker()
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
                        onClicked: {
                            var pos = btnCapital.mapToItem(null, 0, btnCapital.height + 4)
                            if (root.hasViewModel) viewModel.requestOpenCapital(pos.x, pos.y)
                        }
                    }

                    // 5. Order Execution
                    Button {
                        id: btnOrderExec
                        objectName: "btnBacktestOrderExecution"
                        implicitHeight: 34
                        background: Rectangle { color: "#181a24"; border.color: "#2a2d3d"; border.width: 1; radius: 6 }
                        onClicked: {
                            var pos = btnOrderExec.mapToItem(null, 0, btnOrderExec.height + 4)
                            if (root.hasViewModel) viewModel.requestOpenOrderExecution(pos.x, pos.y)
                        }
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
                        id: btnIndicatorPicker
                        objectName: "btnBacktestIndicatorPicker"
                        implicitHeight: 34
                        background: Rectangle { color: "#181a24"; border.color: "#2a2d3d"; border.width: 1; radius: 6 }
                        onClicked: {
                            var pos = btnIndicatorPicker.mapToItem(null, 0, btnIndicatorPicker.height + 4)
                            if (root.hasViewModel) viewModel.requestOpenIndicatorPicker(pos.x, pos.y)
                        }
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
                            Image { source: "image://icons/sliders/accent"; sourceSize: Qt.size(13, 13) }
                            Text { text: "Thông số Chiến lược"; color: Theme.textPrimary; font.pixelSize: 11; font.bold: true }
                        }
                        onClicked: {
                            if (root.hasViewModel) viewModel.requestOpenBotParams(viewModel.selectedStrategyName)
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
                                color: enabled ? ((root.hasViewModel && viewModel.isConfigDirty) ? (runBtnRoot.hovered ? "#fbbf24" : "#f59e0b") : (runBtnRoot.hovered ? "#12e680" : "#10b981")) : "#242736"
                                radius: 6
                                Behavior on color { ColorAnimation { duration: 150 } }
                            }
                            contentItem: RowLayout {
                                spacing: 8
                                anchors.centerIn: parent
                                Image { source: (root.hasViewModel && viewModel.isConfigDirty) ? "image://icons/rotate-ccw/black" : "image://icons/play/black"; sourceSize: Qt.size(13, 13) }
                                Text {
                                    text: (root.hasViewModel && viewModel.isConfigDirty) ? "CẬP NHẬT LẠI" : "CHẠY BACKTEST"
                                    color: "#08090d"
                                    font.pixelSize: 11
                                    font.bold: true
                                    font.letterSpacing: 0.5
                                }
                            }
                        }
                    }
                }
            }

            // ================= ROW 1.5: STALE CONFIG WARNING BANNER (BOT-095B) =================
            Rectangle {
                id: staleBanner
                objectName: "backtestStaleWarningBanner"
                Layout.fillWidth: true
                implicitHeight: visible ? 36 : 0
                visible: root.hasViewModel && viewModel.isConfigDirty
                color: "#2a1c07"
                border.color: "#d97706"
                border.width: 1
                radius: 6
                clip: true

                Behavior on implicitHeight { NumberAnimation { duration: 150 } }
                Behavior on opacity { NumberAnimation { duration: 150 } }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 8

                    Image {
                        source: "image://icons/triangle-alert/warning"
                        sourceSize: Qt.size(14, 14)
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "Cấu hình đã thay đổi (" + (root.hasViewModel ? viewModel.configDiffSummary : "") + "). Kết quả bên dưới chưa được cập nhật."
                        color: "#fbbf24"
                        font.pixelSize: 11
                        font.bold: true
                        elide: Text.ElideRight
                        textFormat: Text.PlainText
                    }

                    Button {
                        implicitHeight: 24
                        implicitWidth: 95
                        text: "Chạy lại"
                        background: Rectangle {
                            color: "#d97706"
                            radius: 4
                        }
                        contentItem: Text {
                            text: "Chạy lại ngay"
                            color: "#08090d"
                            font.pixelSize: 10
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: {
                            if (root.hasViewModel) viewModel.requestRun()
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
                    Accessible.role: Accessible.Button
                    Accessible.name: "Xem giới hạn của lần chạy này"
                    ToolTip.visible: hovered
                    ToolTip.text: "Xem giới hạn của lần chạy này"
                    implicitWidth: 18
                    implicitHeight: 18
                    padding: 0
                    background: Rectangle { color: "transparent" }
                    contentItem: Image {
                        source: "image://icons/info/muted"
                        sourceSize: Qt.size(13, 13)
                        anchors.centerIn: parent
                    }
                    onClicked: { if (root.hasViewModel) viewModel.requestOpenLimitations() }
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
                    onClicked: { if (root.hasViewModel) viewModel.requestOpenExtendedMetrics() }
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
}

