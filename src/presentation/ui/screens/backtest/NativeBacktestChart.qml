import QtQuick
import QmlShared 1.0
import Sagittarius.NativeChart 1.0

// BOT-098F6C — thin declarative wrapper around NativeChartItem: axis ticks,
// crosshair tooltip and dev-FPS display from its own existing properties,
// plus real drag/wheel/pointer gesture handling. All pixel<->candle-index
// math and timezone formatting are delegated to gestureBridge/timezoneBridge
// (registered as QML context properties by NativeBacktestChartHost) rather
// than reimplemented here — this file owns presentation only, never
// business decisions, and never repacks OHLCV/indicator/marker data.
Item {
    id: root
    objectName: "nativeBacktestChart"

    property string displayTimezone: "UTC"
    property int _lastAppliedCandleCount: -1

    // NativeChartItem's C++ updatePaintNode() only ever builds candle/
    // volume/axis/marker geometry — it never paints a background — so
    // without this the widget falls through to QQuickWidget's default
    // white clear color whenever no snapshot has been submitted yet (e.g.
    // sync still in progress/failed). Matches BaseCard's own #base_card
    // QSS background (Palette.BG_CARD / Theme.bgCard) for seamless
    // blending with the card the chart is embedded in.
    Rectangle {
        id: chartBackground
        objectName: "chartBackground"
        anchors.fill: parent
        color: (Theme && Theme.bgCard) ? Theme.bgCard : "#111318"
    }

    NativeChartItem {
        id: chart
        objectName: "nativeChartItem"
        anchors.fill: parent
    }

    // Initial visible window: latest 150 candles, applied once per new
    // snapshot rather than on every property change, so it doesn't fight a
    // user's own pan/zoom on unrelated re-renders. Deferred via
    // Qt.callLater — NativeChartItem::submitSnapshot() emits
    // snapshotChanged() and then unconditionally resets the viewport to
    // the full range itself afterward, so setting it synchronously here
    // would just get silently overwritten the instant this handler returns.
    Connections {
        target: chart
        function onSnapshotChanged() {
            if (chart.candleCount <= 0 || chart.candleCount === root._lastAppliedCandleCount) {
                return
            }
            root._lastAppliedCandleCount = chart.candleCount
            Qt.callLater(function () {
                var visibleCount = Math.min(150, chart.candleCount)
                chart.setViewport(chart.candleCount - visibleCount, chart.candleCount)
            })
        }
    }

    MouseArea {
        id: interactionArea
        objectName: "interactionArea"
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton

        property real dragStartX: 0
        property real dragStartViewportStart: 0
        property real dragStartViewportEnd: 0
        property bool dragging: false

        onPressed: function (mouse) {
            dragging = true
            dragStartX = mouse.x
            dragStartViewportStart = chart.viewportStart
            dragStartViewportEnd = chart.viewportEnd
        }

        onReleased: function (mouse) {
            dragging = false
        }

        onPositionChanged: function (mouse) {
            if (dragging) {
                var panned = gestureBridge.resolveDrag(
                    dragStartViewportStart,
                    dragStartViewportEnd,
                    chart.candleCount,
                    mouse.x - dragStartX,
                    width
                )
                chart.setViewport(panned[0], panned[1])
            } else {
                chart.setCrosshairPosition(mouse.x, mouse.y)
            }
        }

        onExited: {
            dragging = false
            chart.clearCrosshair()
        }

        onWheel: function (wheel) {
            var cursorFraction = width > 0 ? wheel.x / width : 0.5
            var zoomed = gestureBridge.resolveWheel(
                chart.viewportStart,
                chart.viewportEnd,
                chart.candleCount,
                wheel.angleDelta.y / 120.0,
                cursorFraction
            )
            chart.setViewport(zoomed[0], zoomed[1])
        }
    }

    Repeater {
        objectName: "priceAxisTicks"
        model: chart.priceAxisTicks
        Text {
            objectName: "priceAxisTick"
            x: root.width - width - 4
            y: modelData.position * root.height - height / 2
            text: modelData.value.toFixed(2)
            color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e7ecf2"
            font.pixelSize: 11
        }
    }

    Repeater {
        objectName: "timeAxisTicks"
        model: chart.timeAxisTicks
        Text {
            objectName: "timeAxisTick"
            x: modelData.position * root.width - width / 2
            y: root.height - height - 2
            text: timezoneBridge ? timezoneBridge.formatAxisTime(modelData.timestampUtcMs, root.displayTimezone) : ""
            color: Theme && Theme.muted ? Theme.muted : "#8a93a6"
            font.pixelSize: 11
        }
    }

    Text {
        id: crosshairTooltip
        objectName: "crosshairTooltip"
        visible: chart.crosshairVisible
        x: 8
        y: 8
        color: Theme && Theme.textPrimary ? Theme.textPrimary : "#e7ecf2"
        font.pixelSize: 12
        text: {
            if (!chart.crosshairVisible || !timezoneBridge) {
                return ""
            }
            var tooltip = chart.crosshairTooltip
            return timezoneBridge.formatTimestamp(tooltip.timestampUtcMs, root.displayTimezone)
                + "  O:" + tooltip.open.toFixed(2)
                + "  H:" + tooltip.high.toFixed(2)
                + "  L:" + tooltip.low.toFixed(2)
                + "  C:" + tooltip.close.toFixed(2)
        }
    }

    Text {
        id: devFpsOverlay
        objectName: "devFpsOverlay"
        visible: chart.devFpsEnabled
        anchors.right: root.right
        anchors.top: root.top
        anchors.margins: 4
        color: "white"
        text: "FPS " + chart.measuredFps.toFixed(1)
    }
}
