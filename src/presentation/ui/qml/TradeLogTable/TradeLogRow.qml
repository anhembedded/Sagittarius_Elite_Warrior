import QtQuick
import QtQuick.Layouts

// One row of the trade log table. Every field reads `modelData.<key>` —
// already-formatted display text from `trade_log_row_to_qml`
// (backtest/logic/trade_log_row.py), not computed here. `TradeLogVM.rows`
// is a plain list of dicts, not a `QAbstractListModel`, so a delegate
// addresses fields through `modelData` rather than as bare role names
// (contrast `DatabaseStatusRow.qml`, whose model IS a real
// `QAbstractListModel` with declared `roleNames()`).
//
// Clicking the row toggles `modelData.expanded` (`TradeLogVM.toggleExpanded`)
// — entry/exit reason and per-strategy metadata (`BOT-045`), all already
// formatted by `trade_log_row_to_qml`. No column sort yet (NOTES.md).
ColumnLayout {
    id: root
    spacing: 0

    property int timeWidth: 190
    property int sideWidth: 90
    property int priceWidth: 190
    property int sizeWidth: 130

    RowLayout {
        Layout.fillWidth: true
        Layout.preferredHeight: 48
        spacing: 8

        Text {
            objectName: "tradeLogChevron_" + modelData.index
            Layout.leftMargin: 4
            Layout.preferredWidth: 14
            text: modelData.expanded ? "⌄" : "›"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 11
        }

        ColumnLayout {
            Layout.preferredWidth: root.timeWidth
            spacing: 1
            Text {
                objectName: "tradeLogPositionLabel_" + modelData.index
                text: modelData.positionLabel
                textFormat: Text.PlainText
                color: Theme.textPrimary
                font.bold: true
                font.pixelSize: 12
            }
            Text {
                text: modelData.entryTimeText
                textFormat: Text.PlainText
                color: Theme.muted
                font.pixelSize: 10
            }
            Text {
                text: "Thoát: " + modelData.exitTimeText + " · " + modelData.durationText
                textFormat: Text.PlainText
                color: Theme.muted
                font.pixelSize: 10
            }
        }

        Rectangle {
            objectName: "tradeLogSide_" + modelData.index
            Layout.preferredWidth: root.sideWidth
            implicitHeight: 20
            radius: 4
            color: modelData.sideIsLong ? Theme.stateActiveTint : "transparent"
            border.width: 1
            border.color: modelData.sideIsLong ? Theme.success : Theme.danger
            Text {
                anchors.centerIn: parent
                text: modelData.sideLabel
                textFormat: Text.PlainText
                color: modelData.sideIsLong ? Theme.success : Theme.danger
                font.pixelSize: 10
                font.bold: true
            }
        }

        Text {
            Layout.preferredWidth: root.priceWidth
            text: modelData.entryPriceText + "  →  " + modelData.exitPriceText
            textFormat: Text.PlainText
            color: Theme.textPrimary
            font.pixelSize: 11
        }

        Text {
            Layout.preferredWidth: root.sizeWidth
            horizontalAlignment: Text.AlignRight
            text: modelData.positionSizeText
            textFormat: Text.PlainText
            color: Theme.textPrimary
            font.pixelSize: 11
        }

        Text {
            objectName: "tradeLogPnl_" + modelData.index
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignRight
            text: modelData.pnlText
            textFormat: Text.PlainText
            color: modelData.pnlColor
            font.bold: true
            font.pixelSize: 11
        }

        Text {
            objectName: "tradeLogReturn_" + modelData.index
            Layout.preferredWidth: 70
            horizontalAlignment: Text.AlignRight
            text: modelData.returnText
            textFormat: Text.PlainText
            color: modelData.pnlColor
            font.pixelSize: 11
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: vm.toggleExpanded(parseInt(modelData.index))
        }
    }

    ColumnLayout {
        objectName: "tradeLogExpand_" + modelData.index
        Layout.fillWidth: true
        Layout.leftMargin: 22
        Layout.rightMargin: 12
        Layout.bottomMargin: 10
        visible: modelData.expanded
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 24

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    text: "LÝ DO VÀO LỆNH"
                    textFormat: Text.PlainText
                    color: Theme.muted
                    font.pixelSize: 9
                    font.letterSpacing: 0.5
                }
                Text {
                    text: modelData.entryReasonText
                    textFormat: Text.PlainText
                    color: Theme.textPrimary
                    font.pixelSize: 11
                }
                Text {
                    text: modelData.entryTimeText
                    textFormat: Text.PlainText
                    color: Theme.muted
                    font.pixelSize: 10
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    text: "LÝ DO THOÁT LỆNH"
                    textFormat: Text.PlainText
                    color: Theme.muted
                    font.pixelSize: 9
                    font.letterSpacing: 0.5
                }
                Text {
                    text: modelData.exitReasonText
                    textFormat: Text.PlainText
                    color: Theme.textPrimary
                    font.pixelSize: 11
                }
                Text {
                    text: modelData.exitTimeText
                    textFormat: Text.PlainText
                    color: Theme.muted
                    font.pixelSize: 10
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Text {
                    text: "ĐÁNH GIÁ & THỜI LƯỢNG"
                    textFormat: Text.PlainText
                    color: Theme.muted
                    font.pixelSize: 9
                    font.letterSpacing: 0.5
                }
                Row {
                    spacing: 6
                    Rectangle {
                        implicitWidth: durationLabel.implicitWidth + 14
                        implicitHeight: 20
                        radius: 4
                        color: Theme.stateIdleBg
                        border.width: 1
                        border.color: Theme.stateNavBorder
                        Text {
                            id: durationLabel
                            anchors.centerIn: parent
                            text: "Thời lượng " + modelData.durationText
                            textFormat: Text.PlainText
                            color: Theme.textPrimary
                            font.pixelSize: 10
                        }
                    }
                    Repeater {
                        model: modelData.metadataItems
                        Rectangle {
                            implicitWidth: metaLabel.implicitWidth + 14
                            implicitHeight: 20
                            radius: 4
                            color: Theme.stateIdleBg
                            border.width: 1
                            border.color: Theme.stateNavBorder
                            Text {
                                id: metaLabel
                                anchors.centerIn: parent
                                text: modelData.label + " " + modelData.value
                                textFormat: Text.PlainText
                                color: Theme.textPrimary
                                font.pixelSize: 10
                            }
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        Layout.fillWidth: true
        height: 1
        color: Theme.border
    }
}
