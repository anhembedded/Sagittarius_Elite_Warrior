import QtQuick
import QtQuick.Layouts
import "../kit"
import "../DataTable"

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
//
// Column headers + row-list + empty-state skeleton is `DataTable`
// (`BOT-124`) — the `PanelHeader`/subtitle above it and the row delegate
// stay here (BOT-124 §5: what doesn't generalize).
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
        text: vm ? (vm.symbol + " (" + vm.interval + ")  •  " + vm.rowCount + " nến") : ""
        textFormat: Text.PlainText
        color: Theme.muted
        font.pixelSize: 10
    }

    DataTable {
        Layout.fillWidth: true
        Layout.fillHeight: true
        listObjectName: "klineInspectorRows"
        emptyObjectName: "lblKlineInspectorEmpty"
        reuseItems: true
        columns: [
            { key: "time", label: "Thời gian (UTC)", width: root.timeColumnWidth },
            { key: "open", label: "Mở (Open)", width: root.priceColumnWidth, align: "right" },
            { key: "high", label: "Cao (High)", width: root.priceColumnWidth, align: "right" },
            { key: "low", label: "Thấp (Low)", width: root.priceColumnWidth, align: "right" },
            { key: "close", label: "Đóng (Close)", width: root.priceColumnWidth, align: "right" },
            { key: "volume", label: "Khối lượng (Vol)", width: root.volumeColumnWidth, align: "right" },
            { key: "change", label: "Biến động", width: root.changeColumnWidth, align: "right" },
            { key: "trades", label: "Số lệnh", fillWidth: true, align: "right" },
        ]
        rowsModel: vm ? vm.rows : null
        isEmpty: vm ? vm.rows.length === 0 : false
        emptyText: "Không có dữ liệu nến nào trong cơ sở dữ liệu."
        rowDelegate: Component {
            KlineInspectorRow {
                width: ListView.view.width
                timeWidth: root.timeColumnWidth
                priceWidth: root.priceColumnWidth
                volumeWidth: root.volumeColumnWidth
                changeWidth: root.changeColumnWidth
            }
        }
    }
}
