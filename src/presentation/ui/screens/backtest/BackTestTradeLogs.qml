import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0
import "../../components"

Rectangle {
    id: root
    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null
    readonly property color themeAccent: Theme && Theme.accent ? Theme.accent : "#fbbf24"
    readonly property color themeTextPrimary: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
    readonly property color themeMuted: Theme && Theme.muted ? Theme.muted : "#9aa4b2"
    implicitWidth: 1200
    color: "#0d0e14"

    //: BOT-090 — single source of truth for one row's height, referenced
    //: both by the real delegate below and by `minimumUsableHeight`'s
    //: floor calculation, so the two can never drift apart.
    property int rowHeight: 44
    //: BOT-090 — how many trade rows the pane should stay usable for by
    //: default; a page can hold up to PAGE_SIZE=20 rows (trade_log_pagination.py),
    //: which the ListView scrolls through internally (it's a Flickable —
    //: unlike BOT-089's stat cards, a log page has no single "natural"
    //: height to measure). This is a deliberate UX floor, not a rediscovery
    //: of a real content size — same category of choice as BOT-089's
    //: resultColumn ScrollView budget.
    property int minVisibleRows: 5
    //: BOT-090 — read by BackTestView._bind_trade_log_minimum_height() and
    //: applied via QWidget.setMinimumHeight(), so QSplitter can never
    //: squeeze this pane below "usable" the way setSizes([600, 200]) alone
    //: let it (200px < toolbarRow + tableHeader + 20 rows + pagination by
    //: a wide margin — the exact BUG-004 symptom: headers/tabs/pagination
    //: all rendered, zero actual rows visible). Always counts the
    //: pagination row's height even when 1 page of results wouldn't show
    //: it, so the floor doesn't jump depending on result-set size.
    property int panelMargin: 12
    property real minimumUsableHeight:
        panelMargin * 2
        + tabBar.implicitHeight
        + outerColumn.spacing
        + toolbarRow.implicitHeight
        + outerColumn.spacing
        + tableHeaderRow.Layout.preferredHeight
        + minVisibleRows * rowHeight
        + paginationRow.Layout.preferredHeight

    //: Mirrors TradeLogFilter's Python values exactly (trade_log_filter.py)
    readonly property var filterTabs: [
        { value: "all", label: "Tất cả" },
        { value: "long", label: "Mua (LONG)" },
        { value: "short", label: "Bán (SHORT)" },
        { value: "win", label: "Lệnh thắng" },
        { value: "loss", label: "Lệnh thua" }
    ]

    //: Single Source of Truth for Dynamic Responsive Column Widths (proportional to container width)
    readonly property real tableUsableWidth: Math.max(760, root.width - (panelMargin * 2) - 24 - (5 * 8))
    readonly property real col1Width: Math.max(140, tableUsableWidth * 0.17)
    readonly property real col2Width: Math.max(64, tableUsableWidth * 0.08)
    readonly property real col3Width: Math.max(180, tableUsableWidth * 0.28)
    readonly property real col4Width: Math.max(130, tableUsableWidth * 0.18)
    readonly property real col5Width: Math.max(110, tableUsableWidth * 0.16)
    readonly property real col6Width: Math.max(70, tableUsableWidth * 0.13)

    property var expandedRows: ({})

    function toggleTradeLogRow(rowIndex) {
        var next = Object.assign({}, expandedRows)
        next[rowIndex] = !next[rowIndex]
        expandedRows = next
    }

    ColumnLayout {
        id: outerColumn
        anchors.fill: parent
        anchors.margins: root.panelMargin
        spacing: 10

        // ================= TOP DYNAMIC TAB BAR =================
        DynamicTabBar {
            id: tabBar
            objectName: "bottomTabBar"
            Layout.fillWidth: true
            tabsModel: [
                {
                    id: "trades",
                    label: "DANH SÁCH LỆNH",
                    badge: (root.hasViewModel ? viewModel.tradeLogTotalCount : 0) + " LỆNH"
                },
                {
                    id: "logs",
                    label: "NHẬT KÝ BACKTEST",
                    badge: (root.hasViewModel && viewModel.logModel ? viewModel.logModel.rowCount() : 0) + " EVENTS"
                }
            ]
            currentIndex: (root.hasViewModel && viewModel.activeBottomTab === "logs") ? 1 : 0
            onTabSelected: function(index, tabId) {
                if (root.hasViewModel) {
                    viewModel.setActiveBottomTab(tabId)
                }
            }
        }

        // ================= TAB 1: TRADE LOGS CONTAINER =================
        ColumnLayout {
            id: tradeLogsTabContent
            objectName: "tradeLogsTabContent"
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10
            visible: !root.hasViewModel || viewModel.activeBottomTab !== "logs"

            // ================= HEADER & TOOLBAR =================
            RowLayout {
                id: toolbarRow
                objectName: "toolbarRow"
                Layout.fillWidth: true
                spacing: 14

                // Filter tabs
                RowLayout {
                    objectName: "tradeLogFilterTabs"
                spacing: 4

                Repeater {
                    model: root.filterTabs

                    Button {
                        objectName: "tabTradeLogFilter_" + modelData.value
                        implicitHeight: 26
                        background: Rectangle {
                            radius: 6
                            color: root.hasViewModel && viewModel.tradeLogFilter === modelData.value ? "#252838" : "transparent"
                            border.color: root.hasViewModel && viewModel.tradeLogFilter === modelData.value ? "#3d425c" : "transparent"
                            border.width: 1
                        }
                        contentItem: Text {
                            leftPadding: 10
                            rightPadding: 10
                            text: modelData.label
                            color: root.hasViewModel && viewModel.tradeLogFilter === modelData.value ? root.themeTextPrimary : root.themeMuted
                            font.pixelSize: 11
                            font.bold: root.hasViewModel && viewModel.tradeLogFilter === modelData.value
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: { if (root.hasViewModel) viewModel.tradeLogFilter = modelData.value }
                    }
                }
            }

            Item { Layout.fillWidth: true }

            // Search bar
            TextField {
                objectName: "txtTradeLogSearch"
                placeholderText: "🔍  Tìm theo mã, ngày..."
                text: root.hasViewModel ? viewModel.tradeLogSearchText : ""
                color: Theme.textPrimary
                font.pixelSize: 11
                background: Rectangle {
                    color: "#141620"
                    border.color: "#242736"
                    border.width: 1
                    radius: 6
                }
                Layout.preferredWidth: 200
                implicitHeight: 28
                onTextEdited: { if (root.hasViewModel) viewModel.tradeLogSearchText = text }
            }

            Button {
                objectName: "btnTradeLogExport"
                text: "Export CSV"
                implicitHeight: 28
                background: Rectangle {
                    color: "#1c1e2b"
                    border.color: "#30344a"
                    border.width: 1
                    radius: 6
                }
                contentItem: RowLayout {
                    spacing: 6
                    anchors.centerIn: parent
                    Image { source: "image://icons/download/accent"; sourceSize: Qt.size(12, 12) }
                    Text {
                        text: "Export"
                        color: root.themeTextPrimary
                        font.pixelSize: 11
                        font.bold: true
                    }
                }
                onClicked: { if (root.hasViewModel) viewModel.requestTradeLogExport() }
            }
        }

        // ================= TABLE CONTAINER =================
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#12141d"
            border.color: "#222533"
            border.width: 1
            radius: 8

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // Header Row
                Rectangle {
                    id: tableHeaderRow
                    Layout.fillWidth: true
                    Layout.preferredHeight: 34
                    color: "#181a26"
                    border.color: "#222533"
                    border.width: 1
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 8
                        Text { text: "STT / THỜI GIAN"; color: Theme.muted; font.pixelSize: 10; font.bold: true; font.letterSpacing: 0.5; Layout.preferredWidth: root.col1Width; horizontalAlignment: Text.AlignLeft }
                        Text { text: "LOẠI"; color: Theme.muted; font.pixelSize: 10; font.bold: true; font.letterSpacing: 0.5; Layout.preferredWidth: root.col2Width; horizontalAlignment: Text.AlignHCenter }
                        Text { text: "GIÁ VÀO  ➔  GIÁ THOÁT"; color: Theme.muted; font.pixelSize: 10; font.bold: true; font.letterSpacing: 0.5; Layout.preferredWidth: root.col3Width; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft }
                        Text { text: "QUY MÔ / KHỐI LƯỢNG"; color: Theme.muted; font.pixelSize: 10; font.bold: true; font.letterSpacing: 0.5; Layout.preferredWidth: root.col4Width; horizontalAlignment: Text.AlignRight }
                        Text { text: "LÃI / LỖ RÒNG"; color: Theme.muted; font.pixelSize: 10; font.bold: true; font.letterSpacing: 0.5; Layout.preferredWidth: root.col5Width; horizontalAlignment: Text.AlignRight }
                        Text { text: "RETURN"; color: Theme.muted; font.pixelSize: 10; font.bold: true; font.letterSpacing: 0.5; Layout.preferredWidth: root.col6Width; horizontalAlignment: Text.AlignRight }
                    }
                }

                ListView {
                    objectName: "listTradeLogRows"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: root.hasViewModel ? viewModel.tradeLogRows : []
                    delegate: Column {
                        width: parent ? parent.width : 0
                        readonly property bool rowExpanded: root.expandedRows[modelData.index] === true

                        Button {
                            id: rowBtn
                            objectName: "rowTradeLog_" + modelData.index
                            width: parent.width
                            implicitHeight: root.rowHeight
                            onClicked: root.toggleTradeLogRow(modelData.index)
                            background: Rectangle {
                                id: rowBg
                                color: rowBtn.hovered ? "#1e2130" : (index % 2 === 0 ? "#12141d" : "#161823")
                                Behavior on color { ColorAnimation { duration: 100 } }
                            }

                            contentItem: RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                spacing: 8

                                ColumnLayout {
                                    Layout.preferredWidth: root.col1Width
                                    spacing: 2
                                    Text {
                                        text: modelData.positionLabel
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        font.bold: true
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Text {
                                        text: modelData.entryTimeText
                                        color: Theme.muted
                                        font.pixelSize: 10
                                        Layout.fillWidth: true
                                    }
                                }

                                Item {
                                    Layout.preferredWidth: root.col2Width
                                    Layout.fillHeight: true
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: Math.min(58, parent.width)
                                        height: 20
                                        color: modelData.sideText === "SHORT" ? "#2a1215" : "#0a291e"
                                        border.color: modelData.sideText === "SHORT" ? "#f43f5e" : "#10b981"
                                        border.width: 1
                                        radius: 4
                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData.sideText || "LONG"
                                            color: modelData.sideText === "SHORT" ? "#f43f5e" : "#10b981"
                                            font.pixelSize: 10
                                            font.bold: true
                                        }
                                    }
                                }

                                ColumnLayout {
                                    Layout.preferredWidth: root.col3Width
                                    Layout.fillWidth: true
                                    spacing: 2
                                    RowLayout {
                                        spacing: 6
                                        Layout.fillWidth: true
                                        Text {
                                            text: modelData.entryPriceText + "  ➔  " + modelData.exitPriceText
                                            color: Theme.textPrimary
                                            font.pixelSize: 11
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }
                                        RowLayout {
                                            spacing: 3
                                            visible: !!modelData.priceDiffText
                                            Text {
                                                text: modelData.priceDiffIcon || ""
                                                color: modelData.priceDiffColor || Theme.muted
                                                font.pixelSize: 8
                                                font.bold: true
                                            }
                                            Text {
                                                text: modelData.priceDiffText || ""
                                                color: modelData.priceDiffColor || Theme.muted
                                                font.pixelSize: 10
                                                font.bold: true
                                            }
                                        }
                                    }
                                    Text {
                                        text: "Thoát: " + modelData.exitTimeText
                                        color: Theme.muted
                                        font.pixelSize: 10
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                }

                                ColumnLayout {
                                    Layout.preferredWidth: root.col4Width
                                    spacing: 2
                                    Text {
                                        text: modelData.positionSizeText
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        font.bold: true
                                        horizontalAlignment: Text.AlignRight
                                        Layout.fillWidth: true
                                    }
                                    Text {
                                        text: modelData.quantityText
                                        color: Theme.muted
                                        font.pixelSize: 10
                                        horizontalAlignment: Text.AlignRight
                                        Layout.fillWidth: true
                                    }
                                }

                                Item {
                                    Layout.preferredWidth: root.col5Width
                                    Layout.fillHeight: true
                                    Rectangle {
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: Math.min(110, parent.width)
                                        height: 24
                                        color: root._withAlpha(modelData.pnlColor, 0.12)
                                        border.color: root._withAlpha(modelData.pnlColor, 0.4)
                                        border.width: 1
                                        radius: 4
                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData.pnlText
                                            color: modelData.pnlColor
                                            font.pixelSize: 11
                                            font.bold: true
                                        }
                                    }
                                }

                                Text {
                                    text: modelData.returnText
                                    color: modelData.pnlColor
                                    font.pixelSize: 11
                                    font.bold: true
                                    Layout.preferredWidth: root.col6Width
                                    horizontalAlignment: Text.AlignRight
                                }
                            }
                        }

                        // ============ EXPAND ROW ============
                        Rectangle {
                            objectName: "detailTradeLog_" + modelData.index
                            width: parent.width
                            visible: rowExpanded
                            height: visible ? detailContent.implicitHeight + 24 : 0
                            color: "#0f1018"
                            border.color: "#282c3f"
                            border.width: visible ? 1 : 0

                            RowLayout {
                                id: detailContent
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 14
                                spacing: 20

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Text { text: "LÝ DO VÀO LỆNH"; color: Theme.accent; font.pixelSize: 9; font.bold: true; font.letterSpacing: 0.5 }
                                    Text { text: modelData.entryReasonText; color: Theme.textPrimary; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Text { text: "LÝ DO THOÁT LỆNH"; color: Theme.accent; font.pixelSize: 9; font.bold: true; font.letterSpacing: 0.5 }
                                    Text { text: modelData.exitReasonText; color: Theme.textPrimary; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Text { text: "CHỈ SỐ ĐÁNH GIÁ & THỜI LƯỢNG"; color: Theme.accent; font.pixelSize: 9; font.bold: true; font.letterSpacing: 0.5 }
                                    Text { text: "Thời lượng: " + modelData.durationText; color: Theme.textPrimary; font.pixelSize: 11; font.bold: true }
                                    Repeater {
                                        model: modelData.metadataItems
                                        Text {
                                            text: modelData.label + ": " + modelData.value
                                            color: root.themeMuted
                                            font.pixelSize: 11
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Empty state
                    Text {
                        anchors.centerIn: parent
                        visible: !root.hasViewModel || viewModel.tradeLogRows.length === 0
                        text: "Chưa có dữ liệu lệnh giao dịch"
                        color: root.themeMuted
                        font.pixelSize: 12
                    }
                }

                // ================= PAGINATION =================
                RowLayout {
                    id: paginationRow
                    Layout.fillWidth: true
                    Layout.preferredHeight: 34
                    visible: root.hasViewModel && viewModel.tradeLogTotalPages > 1

                    Item { Layout.fillWidth: true }

                    Button {
                        objectName: "btnTradeLogPrevPage"
                        text: "‹  Trang trước"
                        implicitHeight: 26
                        enabled: root.hasViewModel && viewModel.tradeLogCurrentPage > 1
                        background: Rectangle {
                            color: parent.enabled ? "#1c1e2b" : "transparent"
                            radius: 4
                        }
                        contentItem: Text { text: parent.text; color: parent.enabled ? Theme.textPrimary : Theme.muted; font.pixelSize: 11; font.bold: true }
                        onClicked: { if (root.hasViewModel) viewModel.tradeLogCurrentPage = viewModel.tradeLogCurrentPage - 1 }
                    }

                    Rectangle {
                        implicitWidth: pageText.implicitWidth + 16
                        implicitHeight: 22
                        color: "#181a24"
                        radius: 4
                        Text {
                            id: pageText
                            anchors.centerIn: parent
                            text: "Trang " + (root.hasViewModel ? viewModel.tradeLogCurrentPage : 0) + " / " + (root.hasViewModel ? viewModel.tradeLogTotalPages : 0)
                            color: root.themeAccent
                            font.pixelSize: 11
                            font.bold: true
                        }
                    }

                    Button {
                        objectName: "btnTradeLogNextPage"
                        text: "Trang sau  ›"
                        implicitHeight: 26
                        enabled: root.hasViewModel && viewModel.tradeLogCurrentPage < viewModel.tradeLogTotalPages
                        background: Rectangle {
                            color: parent.enabled ? "#1c1e2b" : "transparent"
                            radius: 4
                        }
                        contentItem: Text { text: parent.text; color: parent.enabled ? Theme.textPrimary : Theme.muted; font.pixelSize: 11; font.bold: true }
                        onClicked: { if (root.hasViewModel) viewModel.tradeLogCurrentPage = viewModel.tradeLogCurrentPage + 1 }
                    }

                    Item { Layout.fillWidth: true }
                }
            }
        }
    }

        // ================= TAB 2: BACKTEST EXECUTION LOGS =================
        LogPanel {
            id: backtestLogPanel
            objectName: "backtestLogPanel"
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.hasViewModel && viewModel.activeBottomTab === "logs"
            title: "NHẬT KÝ BACKTEST"
            logModel: root.hasViewModel ? viewModel.logModel : null
        }
    }

    function _withAlpha(hex, alpha) {
        var c = Qt.color(hex)
        return Qt.rgba(c.r, c.g, c.b, alpha)
    }
}

