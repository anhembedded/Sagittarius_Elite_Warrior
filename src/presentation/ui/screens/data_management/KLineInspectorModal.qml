import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0
import "../../components"

ModalDialogCard {
    id: root
    objectName: "klineInspectorModal"

    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

    title: "TRA CỨU DỮ LIỆU NẾN (KLINE INSPECTOR)"
    subtitle: root.hasViewModel
              ? (viewModel.klineInspectorSymbol + " (" + viewModel.klineInspectorInterval + ") • " + viewModel.klineInspectorTotalRecords + " nến • Trang " + viewModel.klineInspectorCurrentPage + "/" + viewModel.klineInspectorTotalPages)
              : ""
    iconSource: "image://icons/database/accent"
    preferredWidth: 840
    preferredHeight: 600

    readonly property real colTimeWidth: 140
    readonly property real colPriceWidth: 80
    readonly property real colVolWidth: 105
    readonly property real colChangeWidth: 75
    readonly property real colTradesWidth: 70

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10

        // ==================================================================
        // 1. Top Controls Bar: Jump to Date & Run Audit
        // ==================================================================
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Rectangle {
                Layout.preferredWidth: 160
                Layout.preferredHeight: 32
                color: "#181a20"
                border.color: Theme.border
                border.width: 1
                radius: 4

                TextInput {
                    id: txtJumpDate
                    anchors.fill: parent
                    anchors.margins: 6
                    color: Theme.textPrimary
                    font.pixelSize: 12
                    verticalAlignment: TextInput.AlignVCenter
                    selectByMouse: true

                    Text {
                        text: "YYYY-MM-DD..."
                        color: Theme.muted
                        font.pixelSize: 12
                        visible: !txtJumpDate.text && !txtJumpDate.activeFocus
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Keys.onReturnPressed: btnJump.clicked()
                }
            }

            Button {
                id: btnJump
                text: "Nhảy tới ngày"
                implicitHeight: 32
                background: Rectangle {
                    color: parent.hovered ? "#2b313a" : "#21262d"
                    border.color: Theme.border
                    border.width: 1
                    radius: 4
                }
                contentItem: Text {
                    text: parent.text
                    color: Theme.textPrimary
                    font.pixelSize: 12
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: {
                    if (root.hasViewModel && txtJumpDate.text) {
                        viewModel.requestKlineJumpToDate(txtJumpDate.text)
                    }
                }
            }

            Item { Layout.fillWidth: true }

            Button {
                id: btnAudit
                text: (root.hasViewModel && viewModel.auditRunning) ? "Đang kiểm định..." : "Kiểm định Dữ liệu (Audit)"
                enabled: root.hasViewModel && !viewModel.auditRunning
                implicitHeight: 32
                background: Rectangle {
                    color: parent.enabled ? (parent.hovered ? "#238636" : "#2ea043") : "#21262d"
                    radius: 4
                }
                contentItem: RowLayout {
                    spacing: 6
                    Image {
                        source: "image://icons/shield/text"
                        sourceSize: Qt.size(14, 14)
                    }
                    Text {
                        text: btnAudit.text
                        color: "#ffffff"
                        font.pixelSize: 12
                        font.bold: true
                    }
                }
                onClicked: {
                    if (root.hasViewModel) {
                        viewModel.requestRunAudit(viewModel.klineInspectorSymbol, viewModel.klineInspectorInterval)
                    }
                }
            }
        }

        // ==================================================================
        // 2. Audit Results Banner
        // ==================================================================
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            visible: root.hasViewModel && viewModel.auditSummaryText !== ""
            color: (root.hasViewModel && viewModel.auditPassed) ? "#0d2818" : "#381214"
            border.color: (root.hasViewModel && viewModel.auditPassed) ? Theme.success : Theme.danger
            border.width: 1
            radius: 4

            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 8

                Text {
                    text: (root.hasViewModel && viewModel.auditPassed) ? "✅" : "⚠️"
                    font.pixelSize: 13
                }

                Text {
                    text: root.hasViewModel ? viewModel.auditSummaryText : ""
                    color: (root.hasViewModel && viewModel.auditPassed) ? Theme.success : "#ff7b72"
                    font.pixelSize: 12
                    font.bold: true
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    textFormat: Text.PlainText
                }
            }
        }

        // ==================================================================
        // 3. Table Header
        // ==================================================================
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 28
            color: "#15171d"
            radius: 4

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 4

                Text { text: "Thời gian (UTC)"; color: Theme.muted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: root.colTimeWidth; Layout.minimumWidth: root.colTimeWidth; elide: Text.ElideRight }
                Text { text: "Mở (Open)"; color: Theme.muted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: root.colPriceWidth; Layout.minimumWidth: root.colPriceWidth; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight }
                Text { text: "Cao (High)"; color: Theme.muted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: root.colPriceWidth; Layout.minimumWidth: root.colPriceWidth; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight }
                Text { text: "Thấp (Low)"; color: Theme.muted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: root.colPriceWidth; Layout.minimumWidth: root.colPriceWidth; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight }
                Text { text: "Đóng (Close)"; color: Theme.muted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: root.colPriceWidth; Layout.minimumWidth: root.colPriceWidth; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight }
                Text { text: "Khối lượng (Vol)"; color: Theme.muted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: root.colVolWidth; Layout.minimumWidth: root.colVolWidth; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight }
                Text { text: "Biến động"; color: Theme.muted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: root.colChangeWidth; Layout.minimumWidth: root.colChangeWidth; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight }
                Text { text: "Số lệnh"; color: Theme.muted; font.pixelSize: 11; font.bold: true; Layout.fillWidth: true; Layout.minimumWidth: root.colTradesWidth; horizontalAlignment: Text.AlignRight; elide: Text.ElideRight }
            }
        }

        // ==================================================================
        // 4. Data Rows Table (ListView)
        // ==================================================================
        ListView {
            id: klineListView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.hasViewModel ? viewModel.klineInspectorModel : null

            Text {
                anchors.centerIn: parent
                visible: klineListView.count === 0
                text: "Không có dữ liệu nến nào trong cơ sở dữ liệu."
                color: Theme.muted
                font.pixelSize: 12
                horizontalAlignment: Text.AlignHCenter
            }

            delegate: Rectangle {
                width: klineListView.width
                height: 28
                color: index % 2 === 0 ? "#12141a" : "#161922"

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 4

                    Text {
                        text: model.formattedTime || ""
                        color: Theme.textPrimary
                        font.pixelSize: 11
                        font.family: "monospace"
                        Layout.preferredWidth: root.colTimeWidth
                        Layout.minimumWidth: root.colTimeWidth
                        elide: Text.ElideRight
                        textFormat: Text.PlainText
                    }

                    Text {
                        text: model.openPrice || "0"
                        color: Theme.textPrimary
                        font.pixelSize: 11
                        font.family: "monospace"
                        Layout.preferredWidth: root.colPriceWidth
                        Layout.minimumWidth: root.colPriceWidth
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideRight
                        textFormat: Text.PlainText
                    }

                    Text {
                        text: model.highPrice || "0"
                        color: Theme.textPrimary
                        font.pixelSize: 11
                        font.family: "monospace"
                        Layout.preferredWidth: root.colPriceWidth
                        Layout.minimumWidth: root.colPriceWidth
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideRight
                        textFormat: Text.PlainText
                    }

                    Text {
                        text: model.lowPrice || "0"
                        color: Theme.textPrimary
                        font.pixelSize: 11
                        font.family: "monospace"
                        Layout.preferredWidth: root.colPriceWidth
                        Layout.minimumWidth: root.colPriceWidth
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideRight
                        textFormat: Text.PlainText
                    }

                    Text {
                        text: model.closePrice || "0"
                        color: model.isBullish ? "#0ecb81" : "#f6465d"
                        font.pixelSize: 11
                        font.bold: true
                        font.family: "monospace"
                        Layout.preferredWidth: root.colPriceWidth
                        Layout.minimumWidth: root.colPriceWidth
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideRight
                        textFormat: Text.PlainText
                    }

                    Text {
                        text: model.volume || "0"
                        color: Theme.muted
                        font.pixelSize: 11
                        font.family: "monospace"
                        Layout.preferredWidth: root.colVolWidth
                        Layout.minimumWidth: root.colVolWidth
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideRight
                        textFormat: Text.PlainText
                    }

                    Text {
                        text: model.changePct || "0.00%"
                        color: model.isBullish ? "#0ecb81" : "#f6465d"
                        font.pixelSize: 11
                        font.family: "monospace"
                        Layout.preferredWidth: root.colChangeWidth
                        Layout.minimumWidth: root.colChangeWidth
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideRight
                        textFormat: Text.PlainText
                    }

                    Text {
                        text: (model.trades || 0) + ""
                        color: Theme.muted
                        font.pixelSize: 11
                        font.family: "monospace"
                        Layout.fillWidth: true
                        Layout.minimumWidth: root.colTradesWidth
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideRight
                        textFormat: Text.PlainText
                    }
                }
            }
        }

        // ==================================================================
        // 5. Bottom Pagination Bar
        // ==================================================================
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            color: "#15171d"
            radius: 4

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                Text {
                    text: root.hasViewModel
                          ? ("Hiển thị " + viewModel.klineInspectorModel.rowCount() + " / " + viewModel.klineInspectorTotalRecords + " nến")
                          : "0 nến"
                    color: Theme.muted
                    font.pixelSize: 11
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: "Số nến/trang:"
                    color: Theme.muted
                    font.pixelSize: 11
                }

                Repeater {
                    model: [50, 100, 200, 500]

                    Button {
                        id: btnPageSize
                        required property int modelData
                        text: modelData + ""
                        implicitWidth: 36
                        implicitHeight: 24
                        readonly property bool isSelected: root.hasViewModel && viewModel.klineInspectorPageSize === modelData
                        background: Rectangle {
                            color: btnPageSize.isSelected ? Theme.accent : (btnPageSize.hovered ? "#2b313a" : "#1a1d26")
                            radius: 3
                        }
                        contentItem: Text {
                            text: btnPageSize.text
                            color: btnPageSize.isSelected ? "#000000" : Theme.textPrimary
                            font.pixelSize: 10
                            font.bold: btnPageSize.isSelected
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: if (root.hasViewModel) viewModel.requestKlinePageSize(modelData)
                    }
                }

                Item { Layout.preferredWidth: 8 }

                Button {
                    text: "<<"
                    implicitWidth: 32
                    implicitHeight: 26
                    enabled: root.hasViewModel && viewModel.klineInspectorCurrentPage > 1
                    onClicked: if (root.hasViewModel) viewModel.requestKlinePage(1)
                }

                Button {
                    text: "<"
                    implicitWidth: 28
                    implicitHeight: 26
                    enabled: root.hasViewModel && viewModel.klineInspectorCurrentPage > 1
                    onClicked: if (root.hasViewModel) viewModel.requestKlinePage(viewModel.klineInspectorCurrentPage - 1)
                }

                Text {
                    text: root.hasViewModel
                          ? ("Trang " + viewModel.klineInspectorCurrentPage + " / " + viewModel.klineInspectorTotalPages)
                          : "Trang 1 / 1"
                    color: Theme.textPrimary
                    font.pixelSize: 11
                    font.bold: true
                }

                Button {
                    text: ">"
                    implicitWidth: 28
                    implicitHeight: 26
                    enabled: root.hasViewModel && viewModel.klineInspectorCurrentPage < viewModel.klineInspectorTotalPages
                    onClicked: if (root.hasViewModel) viewModel.requestKlinePage(viewModel.klineInspectorCurrentPage + 1)
                }

                Button {
                    text: ">>"
                    implicitWidth: 32
                    implicitHeight: 26
                    enabled: root.hasViewModel && viewModel.klineInspectorCurrentPage < viewModel.klineInspectorTotalPages
                    onClicked: if (root.hasViewModel) viewModel.requestKlinePage(viewModel.klineInspectorTotalPages)
                }
            }
        }
    }
}
