import QtQuick
import QtQuick.Layouts
import "../kit"

// The dynamic row of primary performance stat cards
// (`BackTestViewModel.primaryStatCards`) — one `StatCard` (`kit/StatCard.qml`)
// per entry, replacing per-run construction/teardown of the QtWidgets
// `StatCard` (`kit/surfaces/stat_card.py`) `backtest_top_panel.py` used to
// build. Layout only: no `if`/loop/computation here (`qml-rule.md` §1.2) —
// every card's title/value/suffix/badge/tone is already-converted plain
// data from `StatCardRowVM.cards` (see `stat_card_row_vm.py` for the one
// conversion this widget needs, a Python `Tone` enum member to the
// lowercase string `StatCard.qml`'s own `tone`/`badgeTone` properties
// compare against).
//
// Deliberately natural (non-stretched) widths, matching the QtWidgets
// `QHBoxLayout` this replaces: that layout never gave its cards a stretch
// factor either (`layout.addWidget(card)`, no `1`, no trailing
// `addStretch()`), so leftover horizontal space stays empty on the right
// rather than being redistributed across the cards — a `RowLayout` gives
// the same result by simply not setting `Layout.fillWidth` on the delegate.
RowLayout {
    id: root
    objectName: "statCardRow"
    spacing: 12

    Repeater {
        model: vm.cards

        StatCard {
            objectName: "cardMetric_" + index
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: modelData.title
            value: modelData.value
            suffix: modelData.suffix
            badgeText: modelData.badgeText
            tone: modelData.tone
            badgeTone: modelData.badgeTone
        }
    }
}
