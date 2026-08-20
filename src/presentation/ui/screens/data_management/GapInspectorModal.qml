import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.Theme

ModalDialogCard {
    id: root
    objectName: "gapInspectorModal"

    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

    title: "CHI TIẾT LỖ HỔNG DỮ LIỆU (GAP INSPECTOR)"
    subtitle: root.hasViewModel
              ? (viewModel.gapInspectorSymbol + " (" + viewModel.gapInspectorInterval + ") • " + viewModel.gapInspectorTotalGaps + " gaps detected")
              : ""
    iconSource: "image://icons/alert-triangle/warning"
    preferredWidth: 680
    preferredHeight: 520

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // ==================================================================
        // 1. Timeline Coverage Bar
        // ==================================================================
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "TIMELINE COVERAGE"
                    color: Theme.muted
                    font.pixelSize: 10
                    font.bold: true
                    font.letterSpacing: 1
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: root.hasViewModel ? ("Độ phủ: " + viewModel.gapInspectorCoveragePct + "%") : "100%"
                    color: (root.hasViewModel && viewModel.gapInspectorCoveragePct >= 99.0) ? Theme.success : Theme.accent
                    font.pixelSize: 11
                    font.bold: true
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 18
                radius: 4
                color: "#15171e"
                border.color: Theme.border
                border.width: 1
                clip: true

                Row {
                    anchors.fill: parent
                    spacing: 0

                    Repeater {
                        model: root.hasViewModel ? viewModel.coverageSegments : []

                        Rectangle {
                            required property var modelData
                            width: Math.max(2, parent.width * (modelData.ratio || 0.05))
                            height: parent.height
                            color: modelData.is_gap ? Theme.danger : Theme.success
                            opacity: modelData.is_gap ? 0.9 : 0.75

                            ToolTip.visible: segMouseArea.containsMouse
                            ToolTip.text: (modelData.is_gap ? "⚠️ GAP: " : "✅ DATA: ") +
                                          modelData.start_time + " → " + modelData.end_time +
                                          " (" + modelData.candle_count + " nến)"

                            MouseArea {
                                id: segMouseArea
                                anchors.fill: parent
                                hoverEnabled: true
                            }
                        }
                    }
                }
            }
        }

        // ==================================================================
        // 2. Gaps Table Header
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
                spacing: 6

                Repeater {
                    model: [
                        { title: "#", weight: 0.6 },
                        { title: "START (FROM)", weight: 2.5 },
                        { title: "END (TO)", weight: 2.5 },
                        { title: "DURATION", weight: 1.2 },
                        { title: "MISSING", weight: 1.4 },
                        { title: "ACTION", weight: 1.8 }
                    ]
                    Text {
                        required property var modelData
                        text: modelData.title
                        color: Theme.muted
                        font.pixelSize: 10
                        font.bold: true
                        Layout.fillWidth: true
                        Layout.preferredWidth: modelData.weight
                        elide: Text.ElideRight
                    }
                }
            }
        }

        // ==================================================================
        // 3. Gaps ListView
        // ==================================================================
        ListView {
            id: gapListView
            objectName: "gapListView"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.hasViewModel ? viewModel.gapList : []
            spacing: 2

            ScrollBar.vertical: ScrollBar {}

            Text {
                anchors.centerIn: parent
                visible: gapListView.count === 0
                text: "Không có lỗ hổng nào được phát hiện (Dữ liệu liên tục 100%)."
                color: Theme.success
                font.pixelSize: 12
                font.bold: true
            }

            delegate: Rectangle {
                id: gapRow
                width: ListView.view.width
                height: 36
                color: index % 2 === 0 ? "transparent" : "#15171d"
                radius: 4

                required property int index
                required property var modelData

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 6

                    Text {
                        text: String(gapRow.modelData.gap_id || (gapRow.index + 1))
                        color: Theme.muted
                        font.pixelSize: 11
                        Layout.fillWidth: true
                        Layout.preferredWidth: 0.6
                    }

                    Text {
                        text: gapRow.modelData.start_time || ""
                        color: Theme.textPrimary
                        font.pixelSize: 11
                        Layout.fillWidth: true
                        Layout.preferredWidth: 2.5
                        elide: Text.ElideRight
                    }

                    Text {
                        text: gapRow.modelData.end_time || ""
                        color: Theme.textPrimary
                        font.pixelSize: 11
                        Layout.fillWidth: true
                        Layout.preferredWidth: 2.5
                        elide: Text.ElideRight
                    }

                    Text {
                        text: gapRow.modelData.duration_text || ""
                        color: Theme.accent
                        font.pixelSize: 11
                        font.bold: true
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1.2
                    }

                    Text {
                        text: "-" + (gapRow.modelData.missing_candles || 0) + " nến"
                        color: Theme.danger
                        font.pixelSize: 11
                        font.bold: true
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1.4
                    }

                    Button {
                        id: btnRepairRow
                        objectName: "btnRepairGap_" + gapRow.index
                        text: "Vá Gap"
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1.8
                        enabled: root.hasViewModel && viewModel.uiMode === "IDLE"

                        onClicked: {
                            if (root.hasViewModel) {
                                viewModel.requestRepairGap(
                                    viewModel.gapInspectorSymbol,
                                    viewModel.gapInspectorInterval,
                                    gapRow.modelData.fetch_start_time || gapRow.modelData.start_time,
                                    gapRow.modelData.fetch_end_time || gapRow.modelData.end_time
                                )
                            }
                        }

                        contentItem: Text {
                            text: btnRepairRow.text
                            color: Theme.accent
                            font.pixelSize: 10
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            implicitHeight: 24
                            radius: 4
                            color: btnRepairRow.hovered && btnRepairRow.enabled ? "#1f2a3a" : "#131822"
                            border.color: Theme.accent
                            border.width: 1
                        }
                    }
                }
            }
        }

        // ==================================================================
        // 4. Footer Actions
        // ==================================================================
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Text {
                text: root.hasViewModel ? ("Tổng số nến bị thiếu: " + viewModel.gapInspectorTotalMissing + " nến") : ""
                color: Theme.danger
                font.pixelSize: 11
                font.bold: true
            }

            Item { Layout.fillWidth: true }

            Button {
                id: btnRepairAll
                objectName: "btnRepairAllGaps"
                text: "Vá Toàn Bộ Lỗ Hổng (Repair All)"
                enabled: root.hasViewModel && viewModel.uiMode === "IDLE" && (gapListView.count > 0)

                onClicked: {
                    if (root.hasViewModel) {
                        viewModel.requestRepairAllGaps(
                            viewModel.gapInspectorSymbol,
                            viewModel.gapInspectorInterval
                        )
                    }
                }

                contentItem: RowLayout {
                    spacing: 6
                    Image {
                        source: "image://icons/zap/accent"
                        sourceSize.width: 14
                        sourceSize.height: 14
                        Layout.preferredWidth: 14
                        Layout.preferredHeight: 14
                    }
                    Text {
                        text: btnRepairAll.text
                        color: Theme.accent
                        font.pixelSize: 11
                        font.bold: true
                    }
                }
                background: Rectangle {
                    implicitHeight: 32
                    radius: 6
                    color: btnRepairAll.hovered && btnRepairAll.enabled ? "#1f2a3a" : "#131822"
                    border.color: Theme.accent
                    border.width: 1
                }
            }

            Button {
                text: "Đóng"
                onClicked: root.close()

                contentItem: Text {
                    text: "Đóng"
                    color: Theme.textPrimary
                    font.pixelSize: 11
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    implicitHeight: 32
                    implicitWidth: 80
                    radius: 6
                    color: "#1e1e24"
                    border.color: Theme.border
                    border.width: 1
                }
            }
        }
    }
}
