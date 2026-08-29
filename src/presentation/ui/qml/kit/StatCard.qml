import QtQuick
import QtQuick.Layouts

// Shared stat/KPI card — kicker, one headline value, optional unit and
// badge, one caption line. Design spec 2026-08-30: "Kicker, value at 22px
// tabular, unit, one line of context. Colour only on the number, and only
// for P&L. Was: value sizes 20-26px, colour applied to labels too."
//
// A QML port of `kit/surfaces/stat_card.py`'s `StatCard`, not a new shape —
// that widget already has title/value/suffix/badge/caption slots and
// already scopes tone colour to just the value label (`set_value(value,
// tone=...)`), so the spec's complaint ("colour applied to labels too")
// was never true of this widget; it is true of whatever the spec's author
// was comparing it against. What the port actually fixes: `STAT_VALUE`'s
// font size is one fixed role-level constant already, but this makes 22px
// (not a value the QtWidgets role happens to use) the one QML call sites
// share, and extends tone-scoping to the caption line too — the mockup's
// own "TỔNG LÃI/LỖ" example colours both "-8,193.54 USD" and "-81.94%"
// together, since together they express one P&L figure, while its two
// non-P&L cards leave both lines untouched.
ColumnLayout {
    id: root
    objectName: "statCard"
    spacing: 6

    property string title: ""
    property string value: ""
    property string suffix: ""
    property string caption: ""
    property string badgeText: ""
    //: "neutral" | "positive" | "negative" — colours `value` and, only
    //: when not "neutral", `caption` too. Never `title`/`suffix`/the badge.
    property string tone: "neutral"
    //: "neutral" | "positive" | "negative", independent of `tone` — a
    //: badge can carry its own semantic (e.g. a duration warning) unrelated
    //: to whether the headline figure is a gain or a loss.
    property string badgeTone: "neutral"

    readonly property string _valueColor: {
        if (root.tone === "positive") return Theme.success;
        if (root.tone === "negative") return Theme.danger;
        return Theme.textPrimary;
    }
    readonly property string _badgeColor: {
        if (root.badgeTone === "positive") return Theme.success;
        if (root.badgeTone === "negative") return Theme.danger;
        return Theme.textPrimary;
    }

    Text {
        objectName: "statCardTitle"
        text: root.title.toUpperCase()
        textFormat: Text.PlainText
        color: Theme.muted
        font.pixelSize: 10
        font.bold: true
        font.letterSpacing: 0.6
    }

    RowLayout {
        spacing: 6

        Text {
            objectName: "statCardValue"
            text: root.value
            textFormat: Text.PlainText
            color: root._valueColor
            font.pixelSize: 22
            font.bold: true
        }

        Text {
            objectName: "statCardSuffix"
            visible: root.suffix !== ""
            text: root.suffix
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 11
        }

        Rectangle {
            objectName: "statCardBadge"
            visible: root.badgeText !== ""
            radius: 4
            color: "transparent"
            border.width: 1
            border.color: root._badgeColor
            implicitWidth: badgeLabel.implicitWidth + 12
            implicitHeight: 18

            Text {
                id: badgeLabel
                objectName: "statCardBadgeText"
                anchors.centerIn: parent
                text: root.badgeText
                textFormat: Text.PlainText
                color: root._badgeColor
                font.pixelSize: 9
            }
        }

        Item { Layout.fillWidth: true }
    }

    Text {
        objectName: "statCardCaption"
        visible: root.caption !== ""
        text: root.caption
        textFormat: Text.PlainText
        color: root.tone === "neutral" ? Theme.muted : root._valueColor
        font.pixelSize: 11
    }
}
