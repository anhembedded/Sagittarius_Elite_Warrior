#pragma once

#include <QByteArray>
#include <QHoverEvent>
#include <QMetaObject>
#include <QQuickItem>
#include <QString>
#include <QVariantList>
#include <QVariantMap>
#include <QtQml/qqmlregistration.h>

#include <atomic>
#include <memory>
#include <vector>

struct NativeIndicatorRenderSeries final {
    quint32 rgba;
    std::vector<double> values;
};

struct NativeMarkerRenderPoint final {
    quint64 candleIndex;
    double price;
    quint32 rgba;
    quint8 kind;
    quint8 direction;
};

class NativeChartItem : public QQuickItem {
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(quint64 snapshotRevision READ snapshotRevision NOTIFY snapshotChanged FINAL)
    Q_PROPERTY(quint64 candleCount READ candleCount NOTIFY snapshotChanged FINAL)
    Q_PROPERTY(QString lastSnapshotError READ lastSnapshotError NOTIFY lastSnapshotErrorChanged FINAL)
    Q_PROPERTY(quint64 indicatorSnapshotRevision READ indicatorSnapshotRevision NOTIFY indicatorSnapshotChanged FINAL)
    Q_PROPERTY(int indicatorSeriesCount READ indicatorSeriesCount NOTIFY indicatorSnapshotChanged FINAL)
    Q_PROPERTY(QString lastIndicatorSnapshotError READ lastIndicatorSnapshotError NOTIFY lastIndicatorSnapshotErrorChanged FINAL)
    Q_PROPERTY(quint64 markerSnapshotRevision READ markerSnapshotRevision NOTIFY markerSnapshotChanged FINAL)
    Q_PROPERTY(quint64 markerCount READ markerCount NOTIFY markerSnapshotChanged FINAL)
    Q_PROPERTY(QString lastMarkerSnapshotError READ lastMarkerSnapshotError NOTIFY lastMarkerSnapshotErrorChanged FINAL)
    Q_PROPERTY(quint64 renderedRevision READ renderedRevision NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(quint64 geometryBuildCount READ geometryBuildCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(int wickVertexCount READ wickVertexCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(int bodyVertexCount READ bodyVertexCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(int volumeVertexCount READ volumeVertexCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(int indicatorVertexCount READ indicatorVertexCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(quint64 volumeGeometryBuildCount READ volumeGeometryBuildCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(quint64 indicatorGeometryBuildCount READ indicatorGeometryBuildCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(int indicatorPixelColumnCount READ indicatorPixelColumnCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(int markerVertexCount READ markerVertexCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(int displayedMarkerCount READ displayedMarkerCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(int representedMarkerCount READ representedMarkerCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(quint64 markerGeometryBuildCount READ markerGeometryBuildCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(qreal renderDevicePixelRatio READ renderDevicePixelRatio NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(int bullishCandleCount READ bullishCandleCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(int bearishCandleCount READ bearishCandleCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(double priceMinimum READ priceMinimum NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(double priceMaximum READ priceMaximum NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(qreal viewportStart READ viewportStart NOTIFY cameraChanged FINAL)
    Q_PROPERTY(qreal viewportEnd READ viewportEnd NOTIFY cameraChanged FINAL)
    Q_PROPERTY(double visiblePriceMinimum READ visiblePriceMinimum NOTIFY cameraChanged FINAL)
    Q_PROPERTY(double visiblePriceMaximum READ visiblePriceMaximum NOTIFY cameraChanged FINAL)
    Q_PROPERTY(quint64 cameraRevision READ cameraRevision NOTIFY cameraChanged FINAL)
    Q_PROPERTY(quint64 renderedCameraRevision READ renderedCameraRevision NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(quint64 cameraUpdateCount READ cameraUpdateCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(QVariantList priceAxisTicks READ priceAxisTicks NOTIFY cameraChanged FINAL)
    Q_PROPERTY(QVariantList timeAxisTicks READ timeAxisTicks NOTIFY cameraChanged FINAL)
    Q_PROPERTY(QString lastViewportError READ lastViewportError NOTIFY lastViewportErrorChanged FINAL)
    Q_PROPERTY(bool crosshairVisible READ crosshairVisible NOTIFY crosshairChanged FINAL)
    Q_PROPERTY(qint64 crosshairCandleIndex READ crosshairCandleIndex NOTIFY crosshairChanged FINAL)
    Q_PROPERTY(QVariantMap crosshairTooltip READ crosshairTooltip NOTIFY crosshairChanged FINAL)
    Q_PROPERTY(quint64 crosshairRevision READ crosshairRevision NOTIFY crosshairChanged FINAL)
    Q_PROPERTY(bool devFpsEnabled READ devFpsEnabled WRITE setDevFpsEnabled NOTIFY devFpsEnabledChanged FINAL)
    Q_PROPERTY(qreal measuredFps READ measuredFps NOTIFY measuredFpsChanged FINAL)

public:
    explicit NativeChartItem(QQuickItem* parent = nullptr);

    [[nodiscard]] quint64 snapshotRevision() const noexcept;
    [[nodiscard]] quint64 candleCount() const noexcept;
    [[nodiscard]] QString lastSnapshotError() const;
    [[nodiscard]] quint64 indicatorSnapshotRevision() const noexcept;
    [[nodiscard]] int indicatorSeriesCount() const noexcept;
    [[nodiscard]] QString lastIndicatorSnapshotError() const;
    [[nodiscard]] quint64 markerSnapshotRevision() const noexcept;
    [[nodiscard]] quint64 markerCount() const noexcept;
    [[nodiscard]] QString lastMarkerSnapshotError() const;
    [[nodiscard]] quint64 renderedRevision() const noexcept;
    [[nodiscard]] quint64 geometryBuildCount() const noexcept;
    [[nodiscard]] int wickVertexCount() const noexcept;
    [[nodiscard]] int bodyVertexCount() const noexcept;
    [[nodiscard]] int volumeVertexCount() const noexcept;
    [[nodiscard]] int indicatorVertexCount() const noexcept;
    [[nodiscard]] quint64 volumeGeometryBuildCount() const noexcept;
    [[nodiscard]] quint64 indicatorGeometryBuildCount() const noexcept;
    [[nodiscard]] int indicatorPixelColumnCount() const noexcept;
    [[nodiscard]] int markerVertexCount() const noexcept;
    [[nodiscard]] int displayedMarkerCount() const noexcept;
    [[nodiscard]] int representedMarkerCount() const noexcept;
    [[nodiscard]] quint64 markerGeometryBuildCount() const noexcept;
    [[nodiscard]] qreal renderDevicePixelRatio() const noexcept;
    [[nodiscard]] int bullishCandleCount() const noexcept;
    [[nodiscard]] int bearishCandleCount() const noexcept;
    [[nodiscard]] double priceMinimum() const noexcept;
    [[nodiscard]] double priceMaximum() const noexcept;
    [[nodiscard]] qreal viewportStart() const noexcept;
    [[nodiscard]] qreal viewportEnd() const noexcept;
    [[nodiscard]] double visiblePriceMinimum() const noexcept;
    [[nodiscard]] double visiblePriceMaximum() const noexcept;
    [[nodiscard]] quint64 cameraRevision() const noexcept;
    [[nodiscard]] quint64 renderedCameraRevision() const noexcept;
    [[nodiscard]] quint64 cameraUpdateCount() const noexcept;
    [[nodiscard]] QVariantList priceAxisTicks() const;
    [[nodiscard]] QVariantList timeAxisTicks() const;
    [[nodiscard]] QString lastViewportError() const;
    [[nodiscard]] bool crosshairVisible() const noexcept;
    [[nodiscard]] qint64 crosshairCandleIndex() const noexcept;
    [[nodiscard]] QVariantMap crosshairTooltip() const;
    [[nodiscard]] quint64 crosshairRevision() const noexcept;
    [[nodiscard]] bool devFpsEnabled() const noexcept;
    [[nodiscard]] qreal measuredFps() const noexcept;

    Q_INVOKABLE bool submitSnapshot(const QByteArray& packedSnapshot);
    Q_INVOKABLE bool submitIndicatorSnapshot(const QByteArray& packedSnapshot);
    Q_INVOKABLE bool submitMarkerSnapshot(const QByteArray& packedSnapshot);
    Q_INVOKABLE bool setViewport(qreal startIndex, qreal endIndex);
    Q_INVOKABLE bool setCrosshairPosition(qreal x, qreal y);
    Q_INVOKABLE void clearCrosshair();
    void setDevFpsEnabled(bool enabled);

signals:
    void snapshotChanged();
    void lastSnapshotErrorChanged();
    void indicatorSnapshotChanged();
    void lastIndicatorSnapshotErrorChanged();
    void markerSnapshotChanged();
    void lastMarkerSnapshotErrorChanged();
    void renderDiagnosticsChanged();
    void cameraChanged();
    void lastViewportErrorChanged();
    void crosshairChanged();
    void devFpsEnabledChanged();
    void measuredFpsChanged();

protected:
    QSGNode* updatePaintNode(
        QSGNode* oldNode,
        UpdatePaintNodeData* updatePaintNodeData
    ) override;
    void geometryChange(const QRectF& newGeometry, const QRectF& oldGeometry) override;
    void hoverMoveEvent(QHoverEvent* event) override;
    void hoverLeaveEvent(QHoverEvent* event) override;
    void itemChange(ItemChange change, const ItemChangeData& value) override;

private:
    struct Snapshot final {
        quint64 revision;
        quint64 candleCount;
        std::vector<qint64> timestamps;
        std::vector<double> opens;
        std::vector<double> highs;
        std::vector<double> lows;
        std::vector<double> closes;
        std::vector<double> volumes;
        double priceMinimum;
        double priceMaximum;
        int bullishCandleCount;
        int bearishCandleCount;
    };

    struct IndicatorSnapshot final {
        quint64 revision;
        quint64 candleCount;
        std::vector<NativeIndicatorRenderSeries> series;
    };

    struct MarkerSnapshot final {
        quint64 revision;
        quint64 candleCount;
        std::vector<NativeMarkerRenderPoint> markers;
    };

    bool rejectSnapshot(const QString& errorMessage);
    bool rejectIndicatorSnapshot(const QString& errorMessage);
    bool rejectMarkerSnapshot(const QString& errorMessage);
    bool rejectViewport(const QString& errorMessage);
    void applyViewport(qreal startIndex, qreal endIndex);
    void rebuildAxisTicks();
    void publishRenderDiagnostics(
        quint64 revision,
        quint64 cameraRevision,
        quint64 buildCount,
        quint64 cameraUpdateCount,
        int wickVertices,
        int bodyVertices,
        int volumeVertices,
        int indicatorVertices,
        quint64 volumeBuildCount,
        quint64 indicatorBuildCount,
        int indicatorPixelColumns,
        qreal devicePixelRatio,
        int bullishCandles,
        int bearishCandles,
        double priceMinimum,
        double priceMaximum
    );
    void publishMarkerDiagnostics(
        int markerVertices,
        int displayedMarkers,
        int representedMarkers,
        quint64 markerBuildCount
    );
    void handleFrameRendered();
    void publishMeasuredFps(qreal fps);

    std::atomic<std::shared_ptr<const Snapshot>> pendingSnapshot_;
    std::atomic<std::shared_ptr<const IndicatorSnapshot>> pendingIndicatorSnapshot_;
    std::atomic<std::shared_ptr<const MarkerSnapshot>> pendingMarkerSnapshot_;
    std::shared_ptr<const Snapshot> uiSnapshot_;
    std::shared_ptr<const Snapshot> renderSnapshot_;
    std::shared_ptr<const IndicatorSnapshot> uiIndicatorSnapshot_;
    std::shared_ptr<const IndicatorSnapshot> renderIndicatorSnapshot_;
    std::shared_ptr<const MarkerSnapshot> uiMarkerSnapshot_;
    std::shared_ptr<const MarkerSnapshot> renderMarkerSnapshot_;
    quint64 latestRevision_ = 0;
    quint64 candleCount_ = 0;
    QString lastSnapshotError_;
    quint64 latestIndicatorRevision_ = 0;
    int indicatorSeriesCount_ = 0;
    QString lastIndicatorSnapshotError_;
    quint64 latestMarkerRevision_ = 0;
    quint64 markerCount_ = 0;
    QString lastMarkerSnapshotError_;
    quint64 renderedRevision_ = 0;
    quint64 geometryBuildCount_ = 0;
    int wickVertexCount_ = 0;
    int bodyVertexCount_ = 0;
    int volumeVertexCount_ = 0;
    int indicatorVertexCount_ = 0;
    quint64 volumeGeometryBuildCount_ = 0;
    quint64 indicatorGeometryBuildCount_ = 0;
    int indicatorPixelColumnCount_ = 0;
    int markerVertexCount_ = 0;
    int displayedMarkerCount_ = 0;
    int representedMarkerCount_ = 0;
    quint64 markerGeometryBuildCount_ = 0;
    qreal renderDevicePixelRatio_ = 1.0;
    int bullishCandleCount_ = 0;
    int bearishCandleCount_ = 0;
    double priceMinimum_ = 0.0;
    double priceMaximum_ = 0.0;
    qreal viewportStart_ = 0.0;
    qreal viewportEnd_ = 0.0;
    double visiblePriceMinimum_ = 0.0;
    double visiblePriceMaximum_ = 0.0;
    quint64 cameraRevision_ = 0;
    quint64 renderedCameraRevision_ = 0;
    quint64 cameraUpdateCount_ = 0;
    QVariantList priceAxisTicks_;
    QVariantList timeAxisTicks_;
    QString lastViewportError_;
    bool crosshairVisible_ = false;
    qint64 crosshairCandleIndex_ = -1;
    QVariantMap crosshairTooltip_;
    std::atomic<quint64> crosshairRevision_{0};
    std::atomic<qreal> crosshairRenderX_{0.0};
    std::atomic<qreal> crosshairRenderY_{0.0};
    std::atomic<bool> crosshairRenderVisible_{false};
    std::atomic<bool> devFpsEnabled_{false};
    qreal measuredFps_ = 0.0;
    QMetaObject::Connection frameRenderedConnection_;
    qint64 fpsWindowStartedNs_ = 0;
    quint64 fpsWindowFrameCount_ = 0;
};
