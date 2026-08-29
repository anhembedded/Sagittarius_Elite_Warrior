import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../kit"

// QML redesign of "CHỈ SỐ CHI TIẾT BACKTEST" — see NOTES.md for exactly
// which numbers are real (`BacktestMetrics`, unchanged) and which are this
// widget's own invented verdict-badge heuristic. Self-contained modal via
// the shared `kit/DialogShell` — not `QmlOverlay` (unlike `StatGrid`, the
// widget this parallels): standalone and not wired to a screen yet, so
// there is no host to supply `Overlay` chrome (NOTES.md).
DialogShell {
    id: root
    objectName: "metricsDetailPanel"
    title: "Chỉ số chi tiết Backtest"
    onCancelled: vm.requestClose()

    ColumnLayout {
        anchors.fill: parent
        spacing: 16

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "LÃI THÔ VS LỖ THÔ"
                    textFormat: Text.PlainText
                    color: Theme.muted
                    font.pixelSize: 10
                    font.letterSpacing: 0.5
                }
                Item { Layout.fillWidth: true }
                Text {
                    objectName: "lblGrossProfit"
                    text: vm.grossProfitText
                    textFormat: Text.PlainText
                    color: Theme.success
                    font.bold: true
                    font.pixelSize: 12
                }
                Text {
                    text: "  "
                    textFormat: Text.PlainText
                }
                Text {
                    objectName: "lblGrossLoss"
                    text: vm.grossLossText
                    textFormat: Text.PlainText
                    color: Theme.danger
                    font.bold: true
                    font.pixelSize: 12
                }
            }

            Rectangle {
                objectName: "grossProfitLossBar"
                Layout.fillWidth: true
                implicitHeight: 8
                radius: 4
                color: Theme.danger

                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: parent.width * vm.grossProfitShare
                    radius: 4
                    color: Theme.success
                }
            }

            Text {
                objectName: "lblBarCaption"
                Layout.fillWidth: true
                text: vm.barCaption
                textFormat: Text.PlainText
                color: Theme.muted
                font.pixelSize: 10
                wrapMode: Text.Wrap
            }
        }

        ScrollView {
            id: groupsScroll
            objectName: "metricsDetailScroll"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ColumnLayout {
                width: groupsScroll.availableWidth
                spacing: 16

                Repeater {
                    model: vm.groups

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Text {
                                text: modelData.label
                                textFormat: Text.PlainText
                                color: Theme.muted
                                font.pixelSize: 10
                                font.letterSpacing: 0.8
                            }
                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 10
                            rowSpacing: 10

                            Repeater {
                                model: modelData.rows
                                MetricsDetailCard {
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            objectName: "metricsDetailFooter"
            Layout.fillWidth: true
            spacing: 10

            Text {
                objectName: "lblMetricsFooter"
                Layout.fillWidth: true
                text: vm.footerText
                textFormat: Text.PlainText
                color: Theme.muted
                font.pixelSize: 10
            }
            Button {
                objectName: "btnMetricsCopyAll"
                text: "Copy tất cả"
                role: "ghost"
                onClicked: vm.requestCopy()
            }
            Button {
                objectName: "btnMetricsClose"
                text: "Đóng"
                role: "primary"
                onClicked: vm.requestClose()
            }
        }
    }
}
