import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QmlShared 1.0
import "../../components"

// BackTestModals (BOT-088 / BOT-097) — Orchestrator component hosting all modal dialogs
// for the Backtest Screen inside the full-window OverlayHost.
Item {
    id: root
    readonly property bool hasViewModel: typeof viewModel !== "undefined" && viewModel !== null

    // Exposed to OverlayHost to toggle WA_TransparentForMouseEvents
    readonly property bool hasOpenModal: (botParamsDialog !== null && botParamsDialog.visible)
                                       || (extendedMetricsModal !== null && extendedMetricsModal.visible)
                                       || (limitationsModal !== null && limitationsModal.visible)
                                       || (capitalDialog !== null && capitalDialog.visible)
                                       || (indicatorPickerModal !== null && indicatorPickerModal.visible)
                                       || (orderExecutionModal !== null && orderExecutionModal.visible)
                                       || (strategyPickerModal !== null && strategyPickerModal.visible)
                                       || (symbolPickerModal !== null && symbolPickerModal.visible)
                                       || (timeframePickerModal !== null && timeframePickerModal.visible)
                                       || (timeRangePickerModal !== null && timeRangePickerModal.visible)
                                       || (timezonePickerModal !== null && timezonePickerModal.visible)

    Connections {
        target: !root.hasViewModel ? null : viewModel

        function onOpenBotParamsRequested(strategyName) {
            botParamsDialog.strategyName = strategyName
            botParamsDialog.open()
        }

        function onOpenExtendedMetricsRequested() {
            extendedMetricsModal.open()
        }

        function onOpenLimitationsRequested() {
            limitationsModal.open()
        }

        function onOpenCapitalRequested(x, y) {
            capitalDialog.openDialog()
        }

        function onOpenIndicatorPickerRequested(x, y) {
            indicatorPickerModal.open()
        }

        function onOpenOrderExecutionRequested(x, y) {
            orderExecutionModal.open()
        }

        function onOpenStrategyPickerRequested() {
            strategyPickerModal.open()
        }

        function onOpenSymbolPickerRequested() {
            symbolPickerModal.open()
        }

        function onOpenTimeframePickerRequested() {
            timeframePickerModal.open()
        }

        function onOpenTimeRangePickerRequested() {
            timeRangePickerModal.open()
        }

        function onOpenTimezonePickerRequested() {
            timezonePickerModal.open()
        }
    }

    // 1. Initial Capital Dialog
    CapitalDialog {
        id: capitalDialog
        objectName: "capitalDialog"
    }

    // 2. Extended Metrics Modal
    ExtendedMetricsModal {
        id: extendedMetricsModal
        objectName: "extendedMetricsPopup"
    }

    // 3. Limitations Modal
    LimitationsModal {
        id: limitationsModal
        objectName: "limitationsPopup"
    }

    // 4. Dynamic Strategy Properties & Broker Simulator Modal (BOT-104)
    StrategyPropertiesModal {
        id: botParamsDialog
        objectName: "botParamsDialog"
    }

    // 5. Indicator Picker Modal
    IndicatorPickerModal {
        id: indicatorPickerModal
        objectName: "indicatorPickerModal"
    }

    // 6. Order Execution Triggers Modal
    OrderExecutionModal {
        id: orderExecutionModal
        objectName: "orderExecutionModal"
    }

    // 7. Strategy Picker Modal
    StrategyPickerModal {
        id: strategyPickerModal
        objectName: "strategyPickerModal"
    }

    // 8. Timeframe Picker Modal
    TimeframePickerModal {
        id: timeframePickerModal
        objectName: "timeframePickerModal"
    }

    // 11. Symbol Picker Modal (BOT-102)
    SymbolPickerModal {
        id: symbolPickerModal
        objectName: "symbolPickerModal"
    }

    // 9. Time Range Picker Modal
    TimeRangePickerModal {
        id: timeRangePickerModal
        objectName: "timeRangePickerModal"
    }

    // 10. Timezone Picker Modal (BOT-097)
    TimezonePickerModal {
        id: timezonePickerModal
        objectName: "timezonePickerModal"
    }
}
