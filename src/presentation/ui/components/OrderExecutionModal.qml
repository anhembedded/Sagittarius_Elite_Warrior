import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.UI 1.0

// OrderExecutionModal (BOT-074 / BOT-076 / BOT-088) — Modal card for order execution trigger modes.
//
// UI Truthfulness Note:
// - "On bar close" is the bar-by-bar engine (BOT-021). It is mandatory and cannot be
//   directly toggled off (locked: true) — the user leaves it by picking a different mode
//   instead, same as any single-select group.
// - "Trên mỗi tick của thanh lịch sử" is BOT-076's tick-driven Realtime Backtest engine —
//   real, selectable, dispatches RunRealtimeBacktestCommand (locked: false).
// - The remaining 2 modes are NOT this screen's concern and stay locked: "Khi lệnh được
//   khớp" is calc_on_order_fills, BOT-077's scope (a strategy re-run at the moment of fill,
//   not this engine); "Trên mỗi tick của thanh thời gian thực" means a live/real-time bar,
//   i.e. Dev Board — this modal only ever opens from the Backtest screen.
ModalDialogCard {
    id: root
    title: "THỰC THI TẬP LỆNH"
    iconSource: "image://icons/briefcase/accent"
    preferredWidth: 400
    preferredHeight: 250

    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null
    //: Indices into listModel below that this modal actually lets the user
    //: choose between — kept as named constants so nothing else in this file
    //: has to know "2" means Realtime by magic-number coincidence.
    readonly property int barCloseIndex: 0
    readonly property int historicalTickIndex: 2

    function _syncModelFromExecutionMode() {
        if (!root.hasViewModel) {
            return
        }
        var isRealtime = viewModel.executionMode === "HISTORICAL_TICK"
        listModel.setProperty(root.barCloseIndex, "checked", !isRealtime)
        listModel.setProperty(root.historicalTickIndex, "checked", isRealtime)
    }

    Connections {
        target: root.hasViewModel ? viewModel : null
        function onExecutionModeChanged() {
            root._syncModelFromExecutionMode()
        }
    }

    Component.onCompleted: root._syncModelFromExecutionMode()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 4

        Repeater {
            model: ListModel {
                id: listModel
                ListElement {
                    text: "On bar close"; checked: true; locked: true
                    tooltip: ""
                }
                ListElement {
                    text: "Khi lệnh được khớp"; checked: false; locked: true
                    tooltip: ""
                }
                ListElement {
                    text: "Trên mỗi tick của thanh lịch sử"; checked: false; locked: false
                    // Answers the exact confusion a real session hit: syncing
                    // "Toàn bộ lịch sử" beforehand does NOT cover this mode —
                    // 1-second candles are a separate series from 1-minute
                    // ones (different rows, same table), so switching here
                    // triggers a genuinely new sync at tick resolution.
                    tooltip: "Chế độ này dùng nến 1 giây, tách biệt hoàn toàn với nến bạn đã đồng bộ ở khung thời gian khác — sẽ cần đồng bộ lại dữ liệu riêng cho khung 1 giây."
                }
                ListElement {
                    text: "Trên mỗi tick của thanh thời gian thực"; checked: false; locked: true
                    tooltip: ""
                }
            }

            ItemDelegate {
                id: delegateItem
                Layout.fillWidth: true
                implicitHeight: 38
                enabled: !model.locked
                objectName: "chkExecutionTrigger_" + index
                ToolTip.visible: delegateItem.hovered && model.tooltip !== ""
                ToolTip.delay: 400
                ToolTip.text: model.tooltip

                background: Rectangle {
                    color: delegateItem.hovered ? "#1c1e2b" : "transparent"
                    radius: 6
                }

                contentItem: RowLayout {
                    spacing: 10
                    opacity: delegateItem.enabled ? 1.0 : 0.45

                    CheckBox {
                        id: triggerCheckBox
                        objectName: "triggerCheckBox_" + index
                        checked: model.checked
                        enabled: !model.locked
                        onCheckedChanged: {
                            model.checked = checked
                            // Only the Realtime row is interactive (see
                            // barCloseIndex/historicalTickIndex above) — this
                            // single write is both "turn Realtime on" and,
                            // unchecked, "go back to On bar close", exactly
                            // like a 2-option radio group.
                            if (index === root.historicalTickIndex && root.hasViewModel) {
                                viewModel.executionMode = checked ? "HISTORICAL_TICK" : "BAR_CLOSE"
                            }
                        }
                    }

                    Text {
                        text: model.text
                        textFormat: Text.PlainText
                        color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e5e7eb"
                        font.pixelSize: 12
                        Layout.fillWidth: true
                    }

                    Image {
                        source: "image://icons/info/muted"
                        sourceSize: Qt.size(14, 14)
                    }
                }
            }
        }
    }
}
