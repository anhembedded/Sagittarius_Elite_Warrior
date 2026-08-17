#pragma once

#include <QByteArray>
#include <QQuickItem>
#include <QString>
#include <QVariantList>
#include <QtQml/qqmlregistration.h>

#include <atomic>
#include <memory>
#include <vector>

class NativeChartItem : public QQuickItem {
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(quint64 snapshotRevision READ snapshotRevision NOTIFY snapshotChanged FINAL)
    Q_PROPERTY(quint64 candleCount READ candleCount NOTIFY snapshotChanged FINAL)
    Q_PROPERTY(QString lastSnapshotError READ lastSnapshotError NOTIFY lastSnapshotErrorChanged FINAL)
    Q_PROPERTY(quint64 renderedRevision READ renderedRevision NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(quint64 geometryBuildCount READ geometryBuildCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(int wickVertexCount READ wickVertexCount NOTIFY renderDiagnosticsChanged FINAL)
    Q_PROPERTY(int bodyVertexCount READ bodyVertexCount NOTIFY renderDiagnosticsChanged FINAL)
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

public:
    explicit NativeChartItem(QQuickItem* parent = nullptr);

    [[nodiscard]] quint64 snapshotRevision() const noexcept;
    [[nodiscard]] quint64 candleCount() const noexcept;
    [[nodiscard]] QString lastSnapshotError() const;
    [[nodiscard]] quint64 renderedRevision() const noexcept;
    [[nodiscard]] quint64 geometryBuildCount() const noexcept;
    [[nodiscard]] int wickVertexCount() const noexcept;
    [[nodiscard]] int bodyVertexCount() const noexcept;
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

    Q_INVOKABLE bool submitSnapshot(const QByteArray& packedSnapshot);
    Q_INVOKABLE bool setViewport(qreal startIndex, qreal endIndex);

signals:
    void snapshotChanged();
    void lastSnapshotErrorChanged();
    void renderDiagnosticsChanged();
    void cameraChanged();
    void lastViewportErrorChanged();

protected:
    QSGNode* updatePaintNode(
        QSGNode* oldNode,
        UpdatePaintNodeData* updatePaintNodeData
    ) override;
    void geometryChange(const QRectF& newGeometry, const QRectF& oldGeometry) override;

private:
    struct Snapshot final {
        quint64 revision;
        quint64 candleCount;
        std::vector<qint64> timestamps;
        std::vector<double> opens;
        std::vector<double> highs;
        std::vector<double> lows;
        std::vector<double> closes;
        double priceMinimum;
        double priceMaximum;
        int bullishCandleCount;
        int bearishCandleCount;
    };

    bool rejectSnapshot(const QString& errorMessage);
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
        int bullishCandles,
        int bearishCandles,
        double priceMinimum,
        double priceMaximum
    );

    std::atomic<std::shared_ptr<const Snapshot>> pendingSnapshot_;
    std::shared_ptr<const Snapshot> uiSnapshot_;
    std::shared_ptr<const Snapshot> renderSnapshot_;
    quint64 latestRevision_ = 0;
    quint64 candleCount_ = 0;
    QString lastSnapshotError_;
    quint64 renderedRevision_ = 0;
    quint64 geometryBuildCount_ = 0;
    int wickVertexCount_ = 0;
    int bodyVertexCount_ = 0;
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
};
