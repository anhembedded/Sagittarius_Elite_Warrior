import QtQuick
import QtQuick.Layouts

// Shared "long-running task" banner — status caption, a bar that actually
// shows its percentage, and a Cancel action. Design need 2026-08-30:
// `components/app_progress_bar.py`'s `AppProgressBar` already tracks a real
// percent (`backtest_top_panel.py` calls `set_value(int(vm.backtestProgressPercent))`
// every tick) but never renders it — `setTextVisible` stays off by design,
// so the number the ViewModel already computes never reaches the user. This
// component is what "Was: Start Live and Chạy Backtest gave no feedback at
// all" (the mockup's own annotation) asks for instead: the caption, the
// bar, and the percentage it already has, in one place.
//
// Pure QML, no ViewModel (`qml-rule.md` §1.3) — every property here is
// something the host already computes (`backtestProgressText`,
// `backtestProgressPercent`, cancelling state); there is nothing left for a
// widget VM to derive.
ColumnLayout {
    id: root
    objectName: "progressBanner"
    spacing: 4

    property string statusText: ""
    //: 0..100. Ignored while `indeterminate` is true.
    property real percent: 0
    //: The "Đang hủy an toàn..." phase: no known duration, so the bar
    //: pulses instead of claiming a percentage it does not have.
    property bool indeterminate: false
    property bool cancelling: false
    property string cancelLabel: "Hủy"
    signal cancelRequested()

    RowLayout {
        Layout.fillWidth: true
        spacing: 10

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            Text {
                objectName: "progressBannerStatusText"
                Layout.fillWidth: true
                text: root.statusText
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: Theme.textPrimary
                font.pixelSize: 11
            }

            Rectangle {
                id: track
                objectName: "progressBannerTrack"
                Layout.fillWidth: true
                implicitHeight: 6
                radius: 3
                color: Theme.stateIdleBg
                clip: true

                Rectangle {
                    id: fill
                    objectName: "progressBannerFill"
                    radius: 3
                    color: Theme.accent
                    height: parent.height
                    width: root.indeterminate ? track.width * 0.28 : track.width * Math.max(0, Math.min(1, root.percent / 100))
                    visible: !root.indeterminate

                    Behavior on width {
                        enabled: !root.indeterminate
                        NumberAnimation { duration: 150 }
                    }
                }

                Rectangle {
                    objectName: "progressBannerIndeterminateSweep"
                    visible: root.indeterminate
                    radius: 3
                    color: Theme.accent
                    height: parent.height
                    width: track.width * 0.28

                    SequentialAnimation on x {
                        running: root.indeterminate
                        loops: Animation.Infinite
                        NumberAnimation { from: -track.width * 0.28; to: track.width; duration: 900; easing.type: Easing.InOutQuad }
                        NumberAnimation { from: track.width; to: -track.width * 0.28; duration: 0 }
                    }
                }
            }
        }

        Text {
            objectName: "progressBannerPercentText"
            visible: !root.indeterminate
            text: Math.round(root.percent) + "%"
            textFormat: Text.PlainText
            color: Theme.muted
            font.pixelSize: 11
        }

        Button {
            objectName: "progressBannerCancelButton"
            text: root.cancelling ? "Đang hủy..." : root.cancelLabel
            role: "danger"
            enabled: !root.cancelling
            onClicked: root.cancelRequested()
        }
    }
}
