#include "native_chart_item.h"

#include "snapshot_abi.h"

#include <QColor>
#include <QMatrix4x4>
#include <QMetaObject>
#include <QRectF>
#include <QSGFlatColorMaterial>
#include <QSGGeometry>
#include <QSGGeometryNode>
#include <QSGNode>
#include <QSGTransformNode>
#include <QThread>
#include <QVariantMap>
#include <QtEndian>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <memory>
#include <utility>
#include <vector>

namespace {

constexpr float ChartPadding = 4.0F;
constexpr float MinimumBodyPixels = 1.0F;
constexpr float CandleBodyWidthRatio = 0.7F;
constexpr int AxisTickCount = 5;

template <typename Integer>
Integer readLittleEndian(const char* bytes) {
    return qFromLittleEndian<Integer>(reinterpret_cast<const uchar*>(bytes));
}

double readLittleEndianDouble(const char* bytes) {
    const quint64 bits = readLittleEndian<quint64>(bytes);
    double value = 0.0;
    std::memcpy(&value, &bits, sizeof(value));
    return value;
}

QSGGeometryNode* createGeometryNode(
    QSGGeometry::DrawingMode drawingMode,
    const QColor& color
) {
    auto* geometry = new QSGGeometry(QSGGeometry::defaultAttributes_Point2D(), 0);
    geometry->setDrawingMode(drawingMode);
    geometry->setLineWidth(1.0F);

    auto* material = new QSGFlatColorMaterial();
    material->setColor(color);

    auto* node = new QSGGeometryNode();
    node->setGeometry(geometry);
    node->setFlag(QSGNode::OwnsGeometry);
    node->setMaterial(material);
    node->setFlag(QSGNode::OwnsMaterial);
    return node;
}

class ChartRootNode final : public QSGNode {
public:
    ChartRootNode()
        : camera(new QSGTransformNode()),
          bullishWicks(createGeometryNode(QSGGeometry::DrawLines, QColor("#00c087"))),
          bearishWicks(createGeometryNode(QSGGeometry::DrawLines, QColor("#f6465d"))),
          bullishBodies(createGeometryNode(QSGGeometry::DrawTriangles, QColor("#00c087"))),
          bearishBodies(createGeometryNode(QSGGeometry::DrawTriangles, QColor("#f6465d"))) {
        appendChildNode(camera);
        camera->appendChildNode(bullishWicks);
        camera->appendChildNode(bearishWicks);
        camera->appendChildNode(bullishBodies);
        camera->appendChildNode(bearishBodies);
    }

    QSGTransformNode* camera;
    QSGGeometryNode* bullishWicks;
    QSGGeometryNode* bearishWicks;
    QSGGeometryNode* bullishBodies;
    QSGGeometryNode* bearishBodies;
    QSizeF renderedSize;
    quint64 renderedRevision = 0;
    quint64 renderedCameraRevision = 0;
    quint64 buildCount = 0;
    quint64 cameraUpdateCount = 0;
};

void setVertices(
    QSGGeometryNode* node,
    const std::vector<QSGGeometry::Point2D>& vertices
) {
    QSGGeometry* geometry = node->geometry();
    geometry->allocate(static_cast<int>(vertices.size()));
    QSGGeometry::Point2D* destination = geometry->vertexDataAsPoint2D();
    for (std::size_t index = 0; index < vertices.size(); ++index) {
        destination[index].set(vertices[index].x, vertices[index].y);
    }
    node->markDirty(QSGNode::DirtyGeometry | QSGNode::DirtyMaterial);
}

void appendBodyVertices(
    std::vector<QSGGeometry::Point2D>& vertices,
    float left,
    float right,
    float top,
    float bottom
) {
    vertices.push_back({left, top});
    vertices.push_back({right, top});
    vertices.push_back({left, bottom});
    vertices.push_back({right, top});
    vertices.push_back({right, bottom});
    vertices.push_back({left, bottom});
}

void populateGeometry(
    ChartRootNode* root,
    const std::vector<double>& opens,
    const std::vector<double>& highs,
    const std::vector<double>& lows,
    const std::vector<double>& closes,
    double priceMinimum,
    double priceMaximum,
    const QSizeF& size
) {
    const std::size_t candleCount = opens.size();
    std::vector<QSGGeometry::Point2D> bullishWicks;
    std::vector<QSGGeometry::Point2D> bearishWicks;
    std::vector<QSGGeometry::Point2D> bullishBodies;
    std::vector<QSGGeometry::Point2D> bearishBodies;
    bullishWicks.reserve(candleCount * 2U);
    bearishWicks.reserve(candleCount * 2U);
    bullishBodies.reserve(candleCount * 6U);
    bearishBodies.reserve(candleCount * 6U);

    const float height = std::max(0.0F, static_cast<float>(size.height()));
    const float drawableHeight = std::max(0.0F, height - 2.0F * ChartPadding);
    const double priceRange = std::max(0.0, priceMaximum - priceMinimum);
    const float minimumBodyPriceHeight = drawableHeight > 0.0F
        ? static_cast<float>(priceRange / drawableHeight) * MinimumBodyPixels
        : 0.0F;
    const float halfBodyWidth = CandleBodyWidthRatio * 0.5F;

    for (std::size_t index = 0; index < candleCount; ++index) {
        const bool bullish = closes[index] >= opens[index];
        const float centerX = static_cast<float>(index) + 0.5F;
        const float highY = static_cast<float>(highs[index] - priceMinimum);
        const float lowY = static_cast<float>(lows[index] - priceMinimum);
        float openY = static_cast<float>(opens[index] - priceMinimum);
        float closeY = static_cast<float>(closes[index] - priceMinimum);
        if (std::abs(closeY - openY) < minimumBodyPriceHeight) {
            const float midpoint = (openY + closeY) * 0.5F;
            openY = midpoint - minimumBodyPriceHeight * 0.5F;
            closeY = midpoint + minimumBodyPriceHeight * 0.5F;
        }

        auto& wickVertices = bullish ? bullishWicks : bearishWicks;
        wickVertices.push_back({centerX, highY});
        wickVertices.push_back({centerX, lowY});

        auto& bodyVertices = bullish ? bullishBodies : bearishBodies;
        appendBodyVertices(
            bodyVertices,
            centerX - halfBodyWidth,
            centerX + halfBodyWidth,
            std::min(openY, closeY),
            std::max(openY, closeY)
        );
    }

    setVertices(root->bullishWicks, bullishWicks);
    setVertices(root->bearishWicks, bearishWicks);
    setVertices(root->bullishBodies, bullishBodies);
    setVertices(root->bearishBodies, bearishBodies);
}

void updateCameraTransform(
    ChartRootNode* root,
    qreal viewportStart,
    qreal viewportEnd,
    double priceMinimum,
    double priceMaximum,
    const QSizeF& size
) {
    const double viewportSpan = std::max(1.0, viewportEnd - viewportStart);
    const double priceSpan = std::max(
        std::numeric_limits<double>::epsilon(),
        priceMaximum - priceMinimum
    );
    const float width = std::max(0.0F, static_cast<float>(size.width()));
    const float height = std::max(0.0F, static_cast<float>(size.height()));
    const float drawableHeight = std::max(0.0F, height - 2.0F * ChartPadding);
    const float xScale = width / static_cast<float>(viewportSpan);
    const float yScale = drawableHeight / static_cast<float>(priceSpan);

    QMatrix4x4 matrix;
    matrix.setToIdentity();
    matrix(0, 0) = xScale;
    matrix(0, 3) = -static_cast<float>(viewportStart) * xScale;
    matrix(1, 1) = -yScale;
    matrix(1, 3) = ChartPadding + static_cast<float>(priceMaximum) * yScale;
    root->camera->setMatrix(matrix);
}

}  // namespace

NativeChartItem::NativeChartItem(QQuickItem* parent)
    : QQuickItem(parent) {
    setFlag(ItemHasContents, true);
    setClip(true);
}

quint64 NativeChartItem::snapshotRevision() const noexcept {
    return latestRevision_;
}

quint64 NativeChartItem::candleCount() const noexcept {
    return candleCount_;
}

QString NativeChartItem::lastSnapshotError() const {
    return lastSnapshotError_;
}

quint64 NativeChartItem::renderedRevision() const noexcept {
    return renderedRevision_;
}

quint64 NativeChartItem::geometryBuildCount() const noexcept {
    return geometryBuildCount_;
}

int NativeChartItem::wickVertexCount() const noexcept {
    return wickVertexCount_;
}

int NativeChartItem::bodyVertexCount() const noexcept {
    return bodyVertexCount_;
}

int NativeChartItem::bullishCandleCount() const noexcept {
    return bullishCandleCount_;
}

int NativeChartItem::bearishCandleCount() const noexcept {
    return bearishCandleCount_;
}

double NativeChartItem::priceMinimum() const noexcept {
    return priceMinimum_;
}

double NativeChartItem::priceMaximum() const noexcept {
    return priceMaximum_;
}

qreal NativeChartItem::viewportStart() const noexcept {
    return viewportStart_;
}

qreal NativeChartItem::viewportEnd() const noexcept {
    return viewportEnd_;
}

double NativeChartItem::visiblePriceMinimum() const noexcept {
    return visiblePriceMinimum_;
}

double NativeChartItem::visiblePriceMaximum() const noexcept {
    return visiblePriceMaximum_;
}

quint64 NativeChartItem::cameraRevision() const noexcept {
    return cameraRevision_;
}

quint64 NativeChartItem::renderedCameraRevision() const noexcept {
    return renderedCameraRevision_;
}

quint64 NativeChartItem::cameraUpdateCount() const noexcept {
    return cameraUpdateCount_;
}

QVariantList NativeChartItem::priceAxisTicks() const {
    return priceAxisTicks_;
}

QVariantList NativeChartItem::timeAxisTicks() const {
    return timeAxisTicks_;
}

QString NativeChartItem::lastViewportError() const {
    return lastViewportError_;
}

bool NativeChartItem::submitSnapshot(const QByteArray& packedSnapshot) {
    using namespace Sagittarius::NativeChart;

    if (QThread::currentThread() != thread()) {
        return false;
    }
    if (packedSnapshot.size() < SnapshotAbi::HeaderBytes) {
        return rejectSnapshot(QStringLiteral("snapshot is shorter than the v1 header"));
    }

    const char* const bytes = packedSnapshot.constData();
    if (std::memcmp(bytes, SnapshotAbi::Magic, sizeof(SnapshotAbi::Magic)) != 0) {
        return rejectSnapshot(QStringLiteral("snapshot magic must be SGCH"));
    }

    const quint16 version = readLittleEndian<quint16>(bytes + 4);
    const quint16 headerBytes = readLittleEndian<quint16>(bytes + 6);
    const quint64 revision = readLittleEndian<quint64>(bytes + 8);
    const quint64 count = readLittleEndian<quint64>(bytes + 16);

    if (version != SnapshotAbi::Version || headerBytes != SnapshotAbi::HeaderBytes) {
        return rejectSnapshot(QStringLiteral("unsupported chart snapshot ABI"));
    }
    if (revision <= latestRevision_) {
        return rejectSnapshot(QStringLiteral("snapshot revision must increase monotonically"));
    }
    if (count > (std::numeric_limits<quint64>::max() - headerBytes) /
                    SnapshotAbi::BytesPerCandle) {
        return rejectSnapshot(QStringLiteral("snapshot candle count overflows byte size"));
    }

    const quint64 expectedBytes = headerBytes + count * SnapshotAbi::BytesPerCandle;
    if (expectedBytes != static_cast<quint64>(packedSnapshot.size())) {
        return rejectSnapshot(QStringLiteral("snapshot byte size does not match candle count"));
    }

    const std::size_t candleCount = static_cast<std::size_t>(count);
    const std::size_t timestampsOffset = headerBytes;
    const std::size_t opensOffset = timestampsOffset + candleCount * sizeof(qint64);
    const std::size_t highsOffset = opensOffset + candleCount * sizeof(double);
    const std::size_t lowsOffset = highsOffset + candleCount * sizeof(double);
    const std::size_t closesOffset = lowsOffset + candleCount * sizeof(double);
    const std::size_t volumesOffset = closesOffset + candleCount * sizeof(double);

    std::vector<qint64> timestamps(candleCount);
    std::vector<double> opens(candleCount);
    std::vector<double> highs(candleCount);
    std::vector<double> lows(candleCount);
    std::vector<double> closes(candleCount);
    double priceMinimum = 0.0;
    double priceMaximum = 0.0;
    int bullishCandleCount = 0;

    for (std::size_t index = 0; index < candleCount; ++index) {
        const std::size_t byteOffset = index * sizeof(double);
        timestamps[index] = readLittleEndian<qint64>(
            bytes + timestampsOffset + index * sizeof(qint64)
        );
        if (index > 0U && timestamps[index] <= timestamps[index - 1U]) {
            return rejectSnapshot(
                QStringLiteral("snapshot timestamps must increase strictly")
            );
        }
        opens[index] = readLittleEndianDouble(bytes + opensOffset + byteOffset);
        highs[index] = readLittleEndianDouble(bytes + highsOffset + byteOffset);
        lows[index] = readLittleEndianDouble(bytes + lowsOffset + byteOffset);
        closes[index] = readLittleEndianDouble(bytes + closesOffset + byteOffset);
        const double volume = readLittleEndianDouble(
            bytes + volumesOffset + byteOffset
        );
        const bool finiteValues = std::isfinite(opens[index]) &&
            std::isfinite(highs[index]) && std::isfinite(lows[index]) &&
            std::isfinite(closes[index]) && std::isfinite(volume) && volume >= 0.0;
        const bool validEnvelope =
            highs[index] >= std::max(opens[index], closes[index]) &&
            lows[index] <= std::min(opens[index], closes[index]) &&
            highs[index] >= lows[index];
        if (!finiteValues || !validEnvelope) {
            return rejectSnapshot(QStringLiteral("snapshot contains invalid OHLCV values"));
        }
        if (closes[index] >= opens[index]) {
            ++bullishCandleCount;
        }
        if (index == 0U) {
            priceMinimum = lows[index];
            priceMaximum = highs[index];
        } else {
            priceMinimum = std::min(priceMinimum, lows[index]);
            priceMaximum = std::max(priceMaximum, highs[index]);
        }
    }
    if (!std::isfinite(priceMaximum - priceMinimum)) {
        return rejectSnapshot(QStringLiteral("snapshot price range must be finite"));
    }

    auto snapshot = std::make_shared<const Snapshot>(Snapshot{
        revision,
        count,
        std::move(timestamps),
        std::move(opens),
        std::move(highs),
        std::move(lows),
        std::move(closes),
        priceMinimum,
        priceMaximum,
        bullishCandleCount,
        static_cast<int>(count) - bullishCandleCount,
    });
    uiSnapshot_ = snapshot;
    pendingSnapshot_.store(snapshot, std::memory_order_release);
    latestRevision_ = revision;
    candleCount_ = count;
    if (!lastSnapshotError_.isEmpty()) {
        lastSnapshotError_.clear();
        emit lastSnapshotErrorChanged();
    }
    emit snapshotChanged();
    if (count > 0U) {
        applyViewport(0.0, static_cast<qreal>(count));
    } else {
        viewportStart_ = 0.0;
        viewportEnd_ = 0.0;
        visiblePriceMinimum_ = 0.0;
        visiblePriceMaximum_ = 0.0;
        priceAxisTicks_.clear();
        timeAxisTicks_.clear();
        ++cameraRevision_;
        emit cameraChanged();
    }
    update();
    return true;
}

bool NativeChartItem::setViewport(qreal startIndex, qreal endIndex) {
    if (QThread::currentThread() != thread()) {
        return false;
    }
    if (!uiSnapshot_ || uiSnapshot_->candleCount == 0U) {
        return rejectViewport(QStringLiteral("viewport requires a non-empty snapshot"));
    }
    if (!std::isfinite(startIndex) || !std::isfinite(endIndex) ||
        endIndex <= startIndex) {
        return rejectViewport(QStringLiteral("viewport range must be finite and increasing"));
    }

    const qreal candleLimit = static_cast<qreal>(uiSnapshot_->candleCount);
    const qreal clampedStart = std::clamp(startIndex, 0.0, candleLimit);
    const qreal clampedEnd = std::clamp(endIndex, 0.0, candleLimit);
    if (clampedEnd - clampedStart < 1.0) {
        return rejectViewport(QStringLiteral("viewport must contain at least one candle"));
    }
    if (qFuzzyCompare(viewportStart_, clampedStart) &&
        qFuzzyCompare(viewportEnd_, clampedEnd)) {
        return true;
    }

    applyViewport(clampedStart, clampedEnd);
    update();
    return true;
}

QSGNode* NativeChartItem::updatePaintNode(
    QSGNode* oldNode,
    UpdatePaintNodeData* updatePaintNodeData
) {
    Q_UNUSED(updatePaintNodeData);
    auto* root = static_cast<ChartRootNode*>(oldNode);
    if (root == nullptr) {
        root = new ChartRootNode();
    }

    auto pending = pendingSnapshot_.exchange(nullptr, std::memory_order_acq_rel);
    if (pending) {
        renderSnapshot_ = std::move(pending);
    }
    const QSizeF currentSize(width(), height());
    const bool snapshotChanged = renderSnapshot_ &&
        root->renderedRevision != renderSnapshot_->revision;
    const bool sizeChanged = root->renderedSize != currentSize;
    const bool cameraChanged = root->renderedCameraRevision != cameraRevision_;
    if (!renderSnapshot_ || (!snapshotChanged && !sizeChanged && !cameraChanged)) {
        return root;
    }

    if (snapshotChanged || sizeChanged) {
        populateGeometry(
            root,
            renderSnapshot_->opens,
            renderSnapshot_->highs,
            renderSnapshot_->lows,
            renderSnapshot_->closes,
            renderSnapshot_->priceMinimum,
            renderSnapshot_->priceMaximum,
            currentSize
        );
        root->renderedRevision = renderSnapshot_->revision;
        root->renderedSize = currentSize;
        ++root->buildCount;
    }
    if (snapshotChanged || sizeChanged || cameraChanged) {
        updateCameraTransform(
            root,
            viewportStart_,
            viewportEnd_,
            visiblePriceMinimum_ - renderSnapshot_->priceMinimum,
            visiblePriceMaximum_ - renderSnapshot_->priceMinimum,
            currentSize
        );
        root->renderedCameraRevision = cameraRevision_;
        ++root->cameraUpdateCount;
    }

    const int wickVertices = static_cast<int>(renderSnapshot_->candleCount * 2U);
    const int bodyVertices = static_cast<int>(renderSnapshot_->candleCount * 6U);
    const int bullishCandles = renderSnapshot_->bullishCandleCount;
    const int bearishCandles = renderSnapshot_->bearishCandleCount;
    const quint64 renderedRevision = renderSnapshot_->revision;
    const quint64 renderedCameraRevision = root->renderedCameraRevision;
    const quint64 buildCount = root->buildCount;
    const quint64 cameraUpdateCount = root->cameraUpdateCount;
    const double minimum = renderSnapshot_->priceMinimum;
    const double maximum = renderSnapshot_->priceMaximum;
    QMetaObject::invokeMethod(
        this,
        [
            this,
            renderedRevision,
            renderedCameraRevision,
            buildCount,
            cameraUpdateCount,
            wickVertices,
            bodyVertices,
            bullishCandles,
            bearishCandles,
            minimum,
            maximum
        ]() {
            publishRenderDiagnostics(
                renderedRevision,
                renderedCameraRevision,
                buildCount,
                cameraUpdateCount,
                wickVertices,
                bodyVertices,
                bullishCandles,
                bearishCandles,
                minimum,
                maximum
            );
        },
        Qt::QueuedConnection
    );
    return root;
}

void NativeChartItem::geometryChange(
    const QRectF& newGeometry,
    const QRectF& oldGeometry
) {
    QQuickItem::geometryChange(newGeometry, oldGeometry);
    if (newGeometry.size() != oldGeometry.size()) {
        update();
    }
}

bool NativeChartItem::rejectSnapshot(const QString& errorMessage) {
    if (lastSnapshotError_ != errorMessage) {
        lastSnapshotError_ = errorMessage;
        emit lastSnapshotErrorChanged();
    }
    return false;
}

bool NativeChartItem::rejectViewport(const QString& errorMessage) {
    if (lastViewportError_ != errorMessage) {
        lastViewportError_ = errorMessage;
        emit lastViewportErrorChanged();
    }
    return false;
}

void NativeChartItem::applyViewport(qreal startIndex, qreal endIndex) {
    viewportStart_ = startIndex;
    viewportEnd_ = endIndex;

    const std::size_t candleCount = uiSnapshot_->opens.size();
    const std::size_t firstIndex = std::min(
        candleCount - 1U,
        static_cast<std::size_t>(std::floor(startIndex))
    );
    const std::size_t endExclusive = std::min(
        candleCount,
        static_cast<std::size_t>(std::ceil(endIndex))
    );
    visiblePriceMinimum_ = uiSnapshot_->lows[firstIndex];
    visiblePriceMaximum_ = uiSnapshot_->highs[firstIndex];
    for (std::size_t index = firstIndex + 1U; index < endExclusive; ++index) {
        visiblePriceMinimum_ = std::min(
            visiblePriceMinimum_, uiSnapshot_->lows[index]
        );
        visiblePriceMaximum_ = std::max(
            visiblePriceMaximum_, uiSnapshot_->highs[index]
        );
    }
    if (visiblePriceMaximum_ <= visiblePriceMinimum_) {
        const double padding = std::max(
            std::abs(visiblePriceMaximum_) * 1.0e-6,
            1.0e-9
        );
        visiblePriceMinimum_ -= padding;
        visiblePriceMaximum_ += padding;
    }

    rebuildAxisTicks();
    if (!lastViewportError_.isEmpty()) {
        lastViewportError_.clear();
        emit lastViewportErrorChanged();
    }
    ++cameraRevision_;
    emit cameraChanged();
}

void NativeChartItem::rebuildAxisTicks() {
    priceAxisTicks_.clear();
    timeAxisTicks_.clear();

    const double priceSpan = visiblePriceMaximum_ - visiblePriceMinimum_;
    for (int tick = 0; tick < AxisTickCount; ++tick) {
        const double position = static_cast<double>(tick) /
            static_cast<double>(AxisTickCount - 1);
        QVariantMap axisTick;
        axisTick.insert(QStringLiteral("position"), position);
        axisTick.insert(
            QStringLiteral("value"),
            visiblePriceMaximum_ - position * priceSpan
        );
        priceAxisTicks_.append(axisTick);
    }

    const std::size_t candleCount = uiSnapshot_->timestamps.size();
    const std::size_t firstIndex = std::min(
        candleCount - 1U,
        static_cast<std::size_t>(std::floor(viewportStart_))
    );
    const std::size_t lastIndex = std::min(
        candleCount - 1U,
        static_cast<std::size_t>(std::ceil(viewportEnd_) - 1.0)
    );
    const std::size_t visibleCount = lastIndex - firstIndex + 1U;
    const int tickCount = std::min(AxisTickCount, static_cast<int>(visibleCount));
    for (int tick = 0; tick < tickCount; ++tick) {
        const double ratio = tickCount > 1
            ? static_cast<double>(tick) / static_cast<double>(tickCount - 1)
            : 0.5;
        const std::size_t index = firstIndex + static_cast<std::size_t>(
            std::llround(ratio * static_cast<double>(visibleCount - 1U))
        );
        QVariantMap axisTick;
        axisTick.insert(QStringLiteral("position"), ratio);
        axisTick.insert(QStringLiteral("index"), static_cast<qulonglong>(index));
        axisTick.insert(
            QStringLiteral("timestampUtcMs"),
            QVariant::fromValue(uiSnapshot_->timestamps[index])
        );
        timeAxisTicks_.append(axisTick);
    }
}

void NativeChartItem::publishRenderDiagnostics(
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
) {
    if (revision < renderedRevision_ || cameraRevision < renderedCameraRevision_) {
        return;
    }
    renderedRevision_ = revision;
    renderedCameraRevision_ = cameraRevision;
    geometryBuildCount_ = buildCount;
    cameraUpdateCount_ = cameraUpdateCount;
    wickVertexCount_ = wickVertices;
    bodyVertexCount_ = bodyVertices;
    bullishCandleCount_ = bullishCandles;
    bearishCandleCount_ = bearishCandles;
    priceMinimum_ = priceMinimum;
    priceMaximum_ = priceMaximum;
    emit renderDiagnosticsChanged();
}
