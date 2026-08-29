import QtQuick
import QtQuick.Layouts
import "../kit"

// Layout and bindings only (EPIC-015 §3.2). Renders `KlineInspectorVM`'s
// rows — structural pass only: no jump-to-date, no audit banner/button, no
// pagination (replaced by ListView virtualization), see NOTES.md. Column
// headers repeat `_kline_columns.py`'s `_KLINE_COLUMNS` text verbatim —
// same table, not a redesign of its wording. Body for a `QmlOverlay`-style
// host; whichever screen embeds this owns its own chrome.
//
// Header is the shared `kit/PanelHeader` (retrofitted 2026-08-30, see
// `qml/kit/NOTES.md`) — not a hand-rolled accent bar + label anymore. The
// symbol/interval/count line stays a separate subtitle text below it:
// `PanelHeader`'s spec has a title and a count badge, not a subtitle slot.
ColumnLayout {
    id: root
    objectName: "klineInspectorBody"
    spacing: 10

    readonly property int timeColumnWidth: 170
    readonly property int priceColumnWidth: 100
    readonly property int volumeColumnWidth: 110
    readonly property int changeColumnWidth: 90

    PanelHeader {
        Layout.fillWidth: true
        title: "Tra cứu dữ liệu nến (KLine Inspector)"
    }

    Text {
        objectName: "lblKlineInspectorSubtitle"
        Layout.fillWidth: true
        text: vm.symbol + " (" + vm.interval + ")  •  " + vm.rowCount + " nến"
        textFormat: Text.PlainText
        color: Theme.muted
        font.pixelSize: 10
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8

        Text {
            Layout.preferredWidth: root.timeColumnWidth
            text: "Thời gian (UTC)"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
        Text {
            Layout.preferredWidth: root.priceColumnWidth
            horizontalAlignment: Text.AlignRight
            text: "Mở (Open)"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
        Text {
            Layout.preferredWidth: root.priceColumnWidth
            horizontalAlignment: Text.AlignRight
            text: "Cao (High)"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
        Text {
            Layout.preferredWidth: root.priceColumnWidth
            horizontalAlignment: Text.AlignRight
            text: "Thấp (Low)"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
        Text {
            Layout.preferredWidth: root.priceColumnWidth
            horizontalAlignment: Text.AlignRight
            text: "Đóng (Close)"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
        Text {
            Layout.preferredWidth: root.volumeColumnWidth
            horizontalAlignment: Text.AlignRight
            text: "Khối lượng (Vol)"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
        Text {
            Layout.preferredWidth: root.changeColumnWidth
            horizontalAlignment: Text.AlignRight
            text: "Biến động"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignRight
            text: "Số lệnh"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 10
        }
    }

    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

    ListView {
        id: rowsView
        objectName: "klineInspectorRows"
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        reuseItems: true
        model: vm.rows
        delegate: KlineInspectorRow {
            width: rowsView.width
            timeWidth: root.timeColumnWidth
            priceWidth: root.priceColumnWidth
            volumeWidth: root.volumeColumnWidth
            changeWidth: root.changeColumnWidth
        }
    }

    Text {
        objectName: "lblKlineInspectorEmpty"
        Layout.fillWidth: true
        Layout.topMargin: 12
        visible: vm.rows.length === 0
        horizontalAlignment: Text.AlignHCenter
        text: "Không có dữ liệu nến nào trong cơ sở dữ liệu."
        textFormat: Text.PlainText
        color: Theme.muted
        font.pixelSize: 11
    }
}
