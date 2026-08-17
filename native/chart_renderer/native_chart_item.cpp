#include "native_chart_item.h"

#include "snapshot_abi.h"

#include <QColor>
#include <QMetaObject>
#include <QRectF>
#include <QSGFlatColorMaterial>
#include <QSGGeometry>
#include <QSGGeometryNode>
#include <QSGNode>
#include <QThread>
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
constexpr float MinimumBodyHeight = 1.0F;
constexpr float CandleBodyWidthRatio = 0.7F;

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
        : bullishWicks(createGeometryNode(QSGGeometry::DrawLines, QColor("#00c087"))),
          bearishWicks(createGeometryNode(QSGGeometry::DrawLines, QColor("#f6465d"))),
          bullishBodies(createGeometryNode(QSGGeometry::DrawTriangles, QColor("#00c087"))),
          bearishBodies(createGeometryNode(QSGGeometry::DrawTriangles, QColor("#f6465d"))) {
        appendChildNode(bullishWicks);
        appendChildNode(bearishWicks);
        appendChildNode(bullishBodies);
        appendChildNode(bearishBodies);
    }

    QSGGeometryNode* bullishWicks;
    QSGGeometryNode* bearishWicks;
    QSGGeometryNode* bullishBodies;
    QSGGeometryNode* bearishBodies;
    QSizeF renderedSize;
    quint64 renderedRevision = 0;
    quint64 buildCount = 0;
};

float projectPrice(
    double price,
    double minimum,
    double maximum,
    float drawableHeight
) {
    const double priceRange = maximum - minimum;
    if (priceRange <= 0.0) {
        return ChartPadding + drawableHeight * 0.5F;
    }
    const double normalized = (maximum - price) / priceRange;
    return ChartPadding + static_cast<float>(normalized) * drawableHeight;
}

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

    const float width = std::max(0.0F, static_cast<float>(size.width()));
    const float height = std::max(0.0F, static_cast<float>(size.height()));
    const float drawableHeight = std::max(0.0F, height - 2.0F * ChartPadding);
    const float candleStep = candleCount > 0U
        ? width / static_cast<float>(candleCount)
        : 0.0F;
    const float halfBodyWidth = candleStep * CandleBodyWidthRatio * 0.5F;

    for (std::size_t index = 0; index < candleCount; ++index) {
        const bool bullish = closes[index] >= opens[index];
        const float centerX = (static_cast<float>(index) + 0.5F) * candleStep;
        const float highY = projectPrice(
            highs[index], priceMinimum, priceMaximum, drawableHeight
        );
        const float lowY = projectPrice(
            lows[index], priceMinimum, priceMaximum, drawableHeight
        );
        float openY = projectPrice(
            opens[index], priceMinimum, priceMaximum, drawableHeight
        );
        float closeY = projectPrice(
            closes[index], priceMinimum, priceMaximum, drawableHeight
        );
        if (std::abs(closeY - openY) < MinimumBodyHeight) {
            const float midpoint = (openY + closeY) * 0.5F;
            openY = midpoint - MinimumBodyHeight * 0.5F;
            closeY = midpoint + MinimumBodyHeight * 0.5F;
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

}  // namespace

NativeChartItem::NativeChartItem(QQuickItem* parent)
    : QQuickItem(parent) {
    setFlag(ItemHasContents, true);
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

    std::vector<double> opens(candleCount);
    std::vector<double> highs(candleCount);
    std::vector<double> lows(candleCount);
    std::vector<double> closes(candleCount);
    double priceMinimum = 0.0;
    double priceMaximum = 0.0;

    for (std::size_t index = 0; index < candleCount; ++index) {
        const std::size_t byteOffset = index * sizeof(double);
        opens[index] = readLittleEndianDouble(bytes + opensOffset + byteOffset);
        highs[index] = readLittleEndianDouble(bytes + highsOffset + byteOffset);
        lows[index] = readLittleEndianDouble(bytes + lowsOffset + byteOffset);
        closes[index] = readLittleEndianDouble(bytes + closesOffset + byteOffset);
        const double volume = readLittleEndianDouble(
            bytes + volumesOffset + byteOffset
        );
        const bool finiteValues = std::isfinite(opens[index]) &&
            std::isfinite(highs[index]) && std::isfinite(lows[index]) &&
            std::isfinite(closes[index]) && std::isfinite(volume);
        const bool validEnvelope =
            highs[index] >= std::max(opens[index], closes[index]) &&
            lows[index] <= std::min(opens[index], closes[index]) &&
            highs[index] >= lows[index];
        if (!finiteValues || !validEnvelope) {
            return rejectSnapshot(QStringLiteral("snapshot contains invalid OHLCV values"));
        }
        if (index == 0U) {
            priceMinimum = lows[index];
            priceMaximum = highs[index];
        } else {
            priceMinimum = std::min(priceMinimum, lows[index]);
            priceMaximum = std::max(priceMaximum, highs[index]);
        }
    }

    auto snapshot = std::make_shared<const Snapshot>(Snapshot{
        revision,
        count,
        std::move(opens),
        std::move(highs),
        std::move(lows),
        std::move(closes),
        priceMinimum,
        priceMaximum,
    });
    pendingSnapshot_.store(std::move(snapshot), std::memory_order_release);
    latestRevision_ = revision;
    candleCount_ = count;
    if (!lastSnapshotError_.isEmpty()) {
        lastSnapshotError_.clear();
        emit lastSnapshotErrorChanged();
    }
    emit snapshotChanged();
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
    if (!renderSnapshot_ || (!snapshotChanged && !sizeChanged)) {
        return root;
    }

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

    const int wickVertices = static_cast<int>(renderSnapshot_->candleCount * 2U);
    const int bodyVertices = static_cast<int>(renderSnapshot_->candleCount * 6U);
    int bullishCandles = 0;
    for (std::size_t index = 0; index < renderSnapshot_->opens.size(); ++index) {
        if (renderSnapshot_->closes[index] >= renderSnapshot_->opens[index]) {
            ++bullishCandles;
        }
    }
    const int bearishCandles = static_cast<int>(renderSnapshot_->candleCount) -
        bullishCandles;
    const quint64 renderedRevision = renderSnapshot_->revision;
    const quint64 buildCount = root->buildCount;
    const double minimum = renderSnapshot_->priceMinimum;
    const double maximum = renderSnapshot_->priceMaximum;
    QMetaObject::invokeMethod(
        this,
        [
            this,
            renderedRevision,
            buildCount,
            wickVertices,
            bodyVertices,
            bullishCandles,
            bearishCandles,
            minimum,
            maximum
        ]() {
            publishRenderDiagnostics(
                renderedRevision,
                buildCount,
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

void NativeChartItem::publishRenderDiagnostics(
    quint64 revision,
    quint64 buildCount,
    int wickVertices,
    int bodyVertices,
    int bullishCandles,
    int bearishCandles,
    double priceMinimum,
    double priceMaximum
) {
    renderedRevision_ = revision;
    geometryBuildCount_ = buildCount;
    wickVertexCount_ = wickVertices;
    bodyVertexCount_ = bodyVertices;
    bullishCandleCount_ = bullishCandles;
    bearishCandleCount_ = bearishCandles;
    priceMinimum_ = priceMinimum;
    priceMaximum_ = priceMaximum;
    emit renderDiagnosticsChanged();
}
