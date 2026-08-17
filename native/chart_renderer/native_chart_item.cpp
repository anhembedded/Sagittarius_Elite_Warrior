#include "native_chart_item.h"

#include "snapshot_abi.h"

#include <QSGNode>
#include <QThread>
#include <QtEndian>

#include <cstring>
#include <limits>
#include <utility>

namespace {

template <typename Integer>
Integer readLittleEndian(const char* bytes) {
    return qFromLittleEndian<Integer>(reinterpret_cast<const uchar*>(bytes));
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

    auto snapshot = std::make_shared<const Snapshot>(
        Snapshot{revision, count, packedSnapshot}
    );
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
    auto pending = pendingSnapshot_.exchange(nullptr, std::memory_order_acq_rel);
    if (pending) {
        renderSnapshot_ = std::move(pending);
    }
    return oldNode;
}

bool NativeChartItem::rejectSnapshot(const QString& errorMessage) {
    if (lastSnapshotError_ != errorMessage) {
        lastSnapshotError_ = errorMessage;
        emit lastSnapshotErrorChanged();
    }
    return false;
}
