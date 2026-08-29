import QtQuick

// Shared status pill — a label plus an optional coloured dot, tone resolved
// from `Theme` rather than an already-picked colour string. Design need
// 2026-08-30: the dashboard's WS connectivity badge
// (`screens/dashboard/dev_board_panel.py`'s `_ws_status_label` + a bare
// square `QLabel`) is real, correctly wired 4-state feedback
// (`dashboard_presenter.py`'s `_WS_STATUS_BY_MODE`: IDLE/muted,
// LOCKED→"SYNCING"/accent, LIVE/success, ERROR/danger) — but it is ad hoc
// QLabel + inline stylesheet, not a component any other screen could reuse
// for its own two/four-state status. `qml-rule.md` §0.2: build the shared
// shape instead of leaving every future status indicator to hand-roll its
// own pill.
Rectangle {
    id: root
    objectName: "statusPill"

    property string text: ""
    //: "idle" | "active" | "success" | "danger" — the same four states the
    //: WS badge already tracks (SYNCING is "active"), generic enough for any
    //: other two/four-state status this app grows next.
    property string tone: "idle"
    property bool showDot: true

    readonly property string _toneColor: {
        if (root.tone === "success") return Theme.success;
        if (root.tone === "active") return Theme.accent;
        if (root.tone === "danger") return Theme.danger;
        return Theme.muted;
    }

    implicitWidth: row.implicitWidth + 16
    implicitHeight: 22
    radius: height / 2
    color: Theme.stateIdleBg
    border.width: 1
    border.color: root._toneColor

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 6

        Rectangle {
            objectName: "statusPillDot"
            visible: root.showDot
            anchors.verticalCenter: parent.verticalCenter
            width: 6
            height: 6
            radius: 3
            color: root._toneColor
        }

        Text {
            objectName: "statusPillLabel"
            text: root.text
            textFormat: Text.PlainText
            color: root._toneColor
            font.pixelSize: 10
            font.bold: true
        }
    }
}
