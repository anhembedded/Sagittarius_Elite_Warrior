import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0

Rectangle {
    id: root
    implicitWidth: 1200
    implicitHeight: 300
    color: "#0d0e14"

    //: Mirrors TradeLogFilter's Python values exactly (trade_log_filter.py)
    readonly property var filterTabs: [
        { value: "all", label: "Tất cả" },
        { value: "long", label: "Mua (LONG)" },
        { value: "short", label: "Bán (SHORT)" },
        { value: "win", label: "Lệnh thắng" },
        { value: "loss", label: "Lệnh thua" }
    ]

    property var expandedRows: ({})

    function toggleTradeLogRow(rowIndex) {
        var next = Object.assign({}, expandedRows)
        next[rowIndex] = !next[rowIndex]
        expandedRows = next
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        // ================= HEADER & TOOLBAR =================
        RowLayout {
            Layout.fillWidth: true
            spacing: 14

            RowLayout {
                spacing: 8
                Rectangle {
                    width: 3
                    height: 14
                    color: Theme.accent
                    radius: 2
                }
                Text {
                    text: "DANH SÁCH LỆNH GIAO DỊCH"
                    color: Theme.textPrimary
                    font.pixelSize: 12
                    font.bold: true
                    font.letterSpacing: 0.8
                }
            }

            Rectangle {
                width: countLabel.implicitWidth + 18
                height: 22
                color: "#181a24"
                border.color: "#282b3a"
                border.width: 1
                radius: 11
                Text {
                    id: countLabel
                    anchors.centerIn: parent
                    text: viewModel.tradeLogTotalCount + " Lệnh"
                    color: Theme.accent
                    font.pixelSize: 10
                    font.bold: true
                }
            }

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
                            color: viewModel.tradeLogFilter === modelData.value ? "#252838" : "transparent"
                            border.color: viewModel.tradeLogFilter === modelData.value ? "#3d425c" : "transparent"
                            border.width: 1
                        }
                        contentItem: Text {
                            leftPadding: 10
                            rightPadding: 10
                            text: modelData.label
                            color: viewModel.tradeLogFilter === modelData.value ? Theme.textPrimary : Theme.muted
                            font.pixelSize: 11
                            font.bold: viewModel.tradeLogFilter === modelData.value
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: viewModel.tradeLogFilter = modelData.value
                    }
                }
            }

            Item { Layout.fillWidth: true }

            // Search bar
            TextField {
                objectName: "txtTradeLogSearch"
                placeholderText: "🔍  Tìm theo mã, ngày..."
                text: viewModel.tradeLogSearchText
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
                onTextEdited: viewModel.tradeLogSearchText = text
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
                        color: Theme.textPrimary
                        font.pixelSize: 11
                        font.bold: true
                    }
                }
                onClicked: viewModel.requestTradeLogExport()
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
                    Layout.fillWidth: true
                    Layout.preferredHeight: 34
                    color: "#181a26"
                    border.color: "#222533"
                    border.width: 1
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        Text { text: "STT / THỜI GIAN"; color: Theme.muted; font.pixelSize: 10; font.bold: true; font.letterSpacing: 0.5; Layout.preferredWidth: 160 }
                        Text { text: "LOẠI"; color: Theme.muted; font.pixelSize: 10; font.bold: true; font.letterSpacing: 0.5; Layout.preferredWidth: 80 }
                        Text { text: "GIÁ VÀO / THOÁT"; color: Theme.muted; font.pixelSize: 10; font.bold: true; font.letterSpacing: 0.5; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
                        Text { text: "QUY MÔ / KHỐI LƯỢNG"; color: Theme.muted; font.pixelSize: 10; font.bold: true; font.letterSpacing: 0.5; Layout.preferredWidth: 150; horizontalAlignment: Text.AlignRight }
                        Text { text: "LÃI / LỖ RÒNG"; color: Theme.muted; font.pixelSize: 10; font.bold: true; font.letterSpacing: 0.5; Layout.preferredWidth: 120; horizontalAlignment: Text.AlignRight }
                        Text { text: "RETURN"; color: Theme.muted; font.pixelSize: 10; font.bold: true; font.letterSpacing: 0.5; Layout.preferredWidth: 80; horizontalAlignment: Text.AlignRight }
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
                            id: rowBtn
                            objectName: "rowTradeLog_" + modelData.index
                            width: parent.width
                            implicitHeight: 44
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

                                ColumnLayout {
                                    Layout.preferredWidth: 160
                                    spacing: 2
                                    Text { text: modelData.positionLabel; color: Theme.textPrimary; font.pixelSize: 11; font.bold: true; elide: Text.ElideRight }
                                    Text { text: modelData.entryTimeText; color: Theme.muted; font.pixelSize: 10 }
                                }

                                Rectangle {
                                    Layout.preferredWidth: 64
                                    implicitHeight: 20
                                    color: "#0a291e"
                                    border.color: "#10b981"
                                    border.width: 1
                                    radius: 4
                                    Text {
                                        anchors.centerIn: parent
                                        text: "LONG"
                                        color: "#10b981"
                                        font.pixelSize: 10
                                        font.bold: true
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text { text: modelData.entryPriceText + "  ➔  " + modelData.exitPriceText; color: Theme.textPrimary; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignRight }
                                    Text { text: "Thoát: " + modelData.exitTimeText; color: Theme.muted; font.pixelSize: 10; horizontalAlignment: Text.AlignRight }
                                }

                                ColumnLayout {
                                    Layout.preferredWidth: 150
                                    spacing: 2
                                    Text { text: modelData.positionSizeText; color: Theme.textPrimary; font.pixelSize: 11; horizontalAlignment: Text.AlignRight }
                                    Text { text: modelData.quantityText; color: Theme.muted; font.pixelSize: 10; horizontalAlignment: Text.AlignRight }
                                }

                                Rectangle {
                                    Layout.preferredWidth: 110
                                    implicitHeight: 24
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

                                Text { text: modelData.returnText; color: modelData.pnlColor; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: 80; horizontalAlignment: Text.AlignRight }
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
                                    Text { text: modelData.entryReasonText; color: Theme.textPrimary; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true; textFormat: Text.PlainText }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Text { text: "LÝ DO THOÁT LỆNH"; color: Theme.accent; font.pixelSize: 9; font.bold: true; font.letterSpacing: 0.5 }
                                    Text { text: modelData.exitReasonText; color: Theme.textPrimary; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true; textFormat: Text.PlainText }
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
                                            color: Theme.muted
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
                        visible: viewModel.tradeLogRows.length === 0
                        text: "Chưa có dữ liệu lệnh giao dịch"
                        color: Theme.muted
                        font.pixelSize: 12
                    }
                }

                // ================= PAGINATION =================
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 34
                    visible: viewModel.tradeLogTotalPages > 1

                    Item { Layout.fillWidth: true }

                    Button {
                        objectName: "btnTradeLogPrevPage"
                        text: "‹  Trang trước"
                        implicitHeight: 26
                        enabled: viewModel.tradeLogCurrentPage > 1
                        background: Rectangle {
                            color: parent.enabled ? "#1c1e2b" : "transparent"
                            radius: 4
                        }
                        contentItem: Text { text: parent.text; color: parent.enabled ? Theme.textPrimary : Theme.muted; font.pixelSize: 11; font.bold: true }
                        onClicked: viewModel.tradeLogCurrentPage = viewModel.tradeLogCurrentPage - 1
                    }

                    Rectangle {
                        implicitWidth: pageText.implicitWidth + 16
                        implicitHeight: 22
                        color: "#181a24"
                        radius: 4
                        Text {
                            id: pageText
                            anchors.centerIn: parent
                            text: "Trang " + viewModel.tradeLogCurrentPage + " / " + viewModel.tradeLogTotalPages
                            color: Theme.accent
                            font.pixelSize: 11
                            font.bold: true
                        }
                    }

                    Button {
                        objectName: "btnTradeLogNextPage"
                        text: "Trang sau  ›"
                        implicitHeight: 26
                        enabled: viewModel.tradeLogCurrentPage < viewModel.tradeLogTotalPages
                        background: Rectangle {
                            color: parent.enabled ? "#1c1e2b" : "transparent"
                            radius: 4
                        }
                        contentItem: Text { text: parent.text; color: parent.enabled ? Theme.textPrimary : Theme.muted; font.pixelSize: 11; font.bold: true }
                        onClicked: viewModel.tradeLogCurrentPage = viewModel.tradeLogCurrentPage + 1
                    }

                    Item { Layout.fillWidth: true }
                }
            }
        }
    }

    function _withAlpha(hex, alpha) {
        var c = Qt.color(hex)
        return Qt.rgba(c.r, c.g, c.b, alpha)
    }
}

