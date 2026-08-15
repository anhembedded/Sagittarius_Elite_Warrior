import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0
import "../../components"

// ExtendedMetricsModal (BOT-088) — Modal card for displaying the 11 detailed backtest performance metric cards.
ModalDialogCard {
    id: root
    objectName: "extendedMetricsPopup"
    title: "CHỈ SỐ CHI TIẾT BACKTEST"
    iconSource: "image://icons/info/accent"
    width: 480
    height: 606

    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

    ScrollView {
        anchors.fill: parent
        anchors.margins: 16
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        GridLayout {
            width: root.width - 48
            columns: 2
            columnSpacing: 12
            rowSpacing: 12

            Repeater {
                model: root.hasViewModel ? viewModel.extendedStatCards : []
                delegate: MetricCard {
                    objectName: "cardExtendedMetric_" + index
                    Layout.fillWidth: true
                    title: modelData.title
                    value: modelData.value
                    suffix: modelData.suffix
                }
            }
        }
    }
}
