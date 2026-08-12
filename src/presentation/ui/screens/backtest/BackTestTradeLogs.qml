import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

Rectangle {
    id: root
    implicitWidth: 1200
    implicitHeight: 300
    color: Theme.bg

    //: Mirrors TradeLogFilter's Python values exactly (trade_log_filter.py)
    //: — this list IS the tab row, both label and the value written into
    //: viewModel.tradeLogFilter.
    readonly property var filterTabs: [
        { value: "all", label: "Tất cả" },
        { value: "long", label: "Mua (LONG)" },
        { value: "short", label: "Bán (SHORT)" },
        { value: "win", label: "Lệnh thắng" },
        { value: "loss", label: "Lệnh thua" }
    ]

    //: Which rows (keyed by the trade's stable, global `modelData.index`
    //: string) currently have their detail section expanded (BOT-045
    //: §2.2). A plain JS object, not a Set — QML property bindings only
    //: react to whole-value reassignment, so `toggleTradeLogRow` always
    //: replaces it wholesale rather than mutating in place.
    property var expandedRows: ({})

    function toggleTradeLogRow(rowIndex) {
        var next = Object.assign({}, expandedRows)
        next[rowIndex] = !next[rowIndex]
        expandedRows = next
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 10

        // ================= HEADER =================
        RowLayout {
            Layout.fillWidth: true
            spacing: 15

            Text {
                text: "DANH SÁCH LỆNH GIAO DỊCH (TRADE LOGS)"
                color: Theme.textPrimary
                font.pixelSize: 12
                font.bold: true
            }

            Rectangle {
                width: countLabel.implicitWidth + 16
                height: 20
                color: Theme.bgCard
                border.color: Theme.border
                radius: 4
                Text {
                    id: countLabel
                    anchors.centerIn: parent
                    text: viewModel.tradeLogTotalCount + " Lệnh"
                    color: Theme.muted
                    font.pixelSize: 10
                }
            }

            // Filter tabs
            RowLayout {
                objectName: "tradeLogFilterTabs"
                spacing: 5

                Repeater {
                    model: root.filterTabs

                    Button {
                        objectName: "tabTradeLogFilter_" + modelData.value
                        implicitHeight: 24
                        background: Rectangle {
                            radius: 4
                            color: viewModel.tradeLogFilter === modelData.value ? Theme.accent : "transparent"
                        }
                        contentItem: Text {
                            text: modelData.label
                            color: viewModel.tradeLogFilter === modelData.value ? "#000000" : Theme.muted
                            font.pixelSize: 11
                            font.bold: viewModel.tradeLogFilter === modelData.value
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: viewModel.tradeLogFilter = modelData.value
                    }
                }
            }

            Item { Layout.fillWidth: true } // Spacer

            // Search bar
            TextField {
                objectName: "txtTradeLogSearch"
                placeholderText: "Tìm theo mã lệnh, ngày..."
                text: viewModel.tradeLogSearchText
                color: Theme.textPrimary
                font.pixelSize: 11
                background: FieldBackground {}
                Layout.preferredWidth: 200
                onTextEdited: viewModel.tradeLogSearchText = text
            }

            Button {
                objectName: "btnTradeLogExport"
                text: "Export"
                implicitHeight: 26
                background: Rectangle { color: "#25262B"; border.color: Theme.border; radius: 4 }
                contentItem: Text {
                    text: parent.text
                    color: Theme.textPrimary
                    font.pixelSize: 11
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: viewModel.requestTradeLogExport()
            }
        }

        // ================= TABLE =================
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.bgCard
            border.color: Theme.border
            border.width: 1
            radius: 4

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // Header Row
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 30
                    color: "#1e1e24"
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        Text { text: "STT / Tên lệnh"; color: Theme.muted; font.pixelSize: 10; Layout.preferredWidth: 150 }
                        Text { text: "Loại"; color: Theme.muted; font.pixelSize: 10; Layout.preferredWidth: 100 }
                        Text { text: "Ngày giờ"; color: Theme.muted; font.pixelSize: 10; Layout.preferredWidth: 150 }
                        Text { text: "Giá vào/thoát"; color: Theme.muted; font.pixelSize: 10; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
                        Text { text: "Quy mô"; color: Theme.muted; font.pixelSize: 10; Layout.preferredWidth: 100; horizontalAlignment: Text.AlignRight }
                        Text { text: "Lãi/Lỗ ròng"; color: Theme.muted; font.pixelSize: 10; Layout.preferredWidth: 100; horizontalAlignment: Text.AlignRight }
                        Text { text: "Return"; color: Theme.muted; font.pixelSize: 10; Layout.preferredWidth: 60; horizontalAlignment: Text.AlignRight }
                    }
                }

                ListView {
                    objectName: "listTradeLogRows"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: viewModel.tradeLogRows
                    delegate: Column {
                        width: parent ? parent.width : 0
                        readonly property bool rowExpanded: root.expandedRows[modelData.index] === true

                        Button {
                            objectName: "rowTradeLog_" + modelData.index
                            width: parent.width
                            implicitHeight: 40
                            background: Rectangle {
                                color: index % 2 === 0 ? "transparent" : "#17181d"
                            }
                            contentItem: RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10

                                // "#26a69a" mirrors chart_card/theme.py's BULL_COLOR — every
                                // trade is a long entry (PaperExchange is long-only, BOT-021),
                                // not tied to this trade's own win/loss (that's pnlColor below).
                                Text { text: modelData.positionLabel; color: "#26a69a"; font.pixelSize: 11; Layout.preferredWidth: 150; elide: Text.ElideRight }
                                Text { text: "Vào\nThoát"; color: Theme.textPrimary; font.pixelSize: 11; Layout.preferredWidth: 100 }
                                Text { text: modelData.entryTimeText + "\n" + modelData.exitTimeText; color: Theme.textPrimary; font.pixelSize: 10; Layout.preferredWidth: 150 }
                                Text { text: modelData.entryPriceText + "\n" + modelData.exitPriceText; color: Theme.textPrimary; font.pixelSize: 11; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
                                Text { text: modelData.positionSizeText + "\n" + modelData.quantityText; color: Theme.textPrimary; font.pixelSize: 11; Layout.preferredWidth: 100; horizontalAlignment: Text.AlignRight }
                                Text { text: modelData.pnlText; color: modelData.pnlColor; font.pixelSize: 11; Layout.preferredWidth: 100; horizontalAlignment: Text.AlignRight }
                                Text { text: modelData.returnText; color: modelData.pnlColor; font.pixelSize: 11; Layout.preferredWidth: 60; horizontalAlignment: Text.AlignRight }
                            }
                            onClicked: root.toggleTradeLogRow(modelData.index)
                        }

                        // ============ EXPAND ROW (BOT-045 §2.2) ============
                        Rectangle {
                            objectName: "detailTradeLog_" + modelData.index
                            width: parent.width
                            visible: rowExpanded
                            height: visible ? detailContent.implicitHeight + 20 : 0
                            color: "#111318"
                            border.color: Theme.border
                            border.width: visible ? 1 : 0

                            RowLayout {
                                id: detailContent
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 10
                                spacing: 20

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Text { text: "LÝ DO VÀO LỆNH"; color: Theme.muted; font.pixelSize: 9; font.bold: true }
                                    Text { text: modelData.entryReasonText; color: Theme.textPrimary; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Text { text: "LÝ DO THOÁT LỆNH"; color: Theme.muted; font.pixelSize: 9; font.bold: true }
                                    Text { text: modelData.exitReasonText; color: Theme.textPrimary; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Text { text: "CHỈ SỐ ĐÁNH GIÁ & THỜI LƯỢNG"; color: Theme.muted; font.pixelSize: 9; font.bold: true }
                                    Text { text: "Thời lượng: " + modelData.durationText; color: Theme.textPrimary; font.pixelSize: 11 }
                                    Repeater {
                                        model: modelData.metadataItems
                                        Text {
                                            text: modelData.label + ": " + modelData.value
                                            color: Theme.textPrimary
                                            font.pixelSize: 11
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Empty state — no run yet, or the current filter/search matches nothing.
                    Text {
                        anchors.centerIn: parent
                        visible: viewModel.tradeLogRows.length === 0
                        text: "Chưa có lệnh nào"
                        color: Theme.muted
                        font.pixelSize: 12
                    }
                }

                // ================= PAGINATION =================
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 30
                    visible: viewModel.tradeLogTotalPages > 1

                    Item { Layout.fillWidth: true }

                    Button {
                        objectName: "btnTradeLogPrevPage"
                        text: "‹ Trước"
                        implicitHeight: 24
                        enabled: viewModel.tradeLogCurrentPage > 1
                        background: Rectangle { color: "transparent" }
                        contentItem: Text { text: parent.text; color: parent.enabled ? Theme.textPrimary : Theme.muted; font.pixelSize: 11 }
                        onClicked: viewModel.tradeLogCurrentPage = viewModel.tradeLogCurrentPage - 1
                    }

                    Text {
                        text: "Trang " + viewModel.tradeLogCurrentPage + " / " + viewModel.tradeLogTotalPages
                        color: Theme.muted
                        font.pixelSize: 11
                    }

                    Button {
                        objectName: "btnTradeLogNextPage"
                        text: "Sau ›"
                        implicitHeight: 24
                        enabled: viewModel.tradeLogCurrentPage < viewModel.tradeLogTotalPages
                        background: Rectangle { color: "transparent" }
                        contentItem: Text { text: parent.text; color: parent.enabled ? Theme.textPrimary : Theme.muted; font.pixelSize: 11 }
                        onClicked: viewModel.tradeLogCurrentPage = viewModel.tradeLogCurrentPage + 1
                    }

                    Item { Layout.fillWidth: true }
                }
            }
        }
    }
}
