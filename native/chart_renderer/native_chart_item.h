#pragma once

#include <QByteArray>
#include <QQuickItem>
#include <QString>
#include <QtQml/qqmlregistration.h>

#include <atomic>
#include <memory>

class NativeChartItem : public QQuickItem {
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(quint64 snapshotRevision READ snapshotRevision NOTIFY snapshotChanged FINAL)
    Q_PROPERTY(quint64 candleCount READ candleCount NOTIFY snapshotChanged FINAL)
    Q_PROPERTY(QString lastSnapshotError READ lastSnapshotError NOTIFY lastSnapshotErrorChanged FINAL)

public:
    explicit NativeChartItem(QQuickItem* parent = nullptr);

    [[nodiscard]] quint64 snapshotRevision() const noexcept;
    [[nodiscard]] quint64 candleCount() const noexcept;
    [[nodiscard]] QString lastSnapshotError() const;

    Q_INVOKABLE bool submitSnapshot(const QByteArray& packedSnapshot);

signals:
    void snapshotChanged();
    void lastSnapshotErrorChanged();

protected:
    QSGNode* updatePaintNode(
        QSGNode* oldNode,
        UpdatePaintNodeData* updatePaintNodeData
    ) override;

private:
    struct Snapshot final {
        quint64 revision;
        quint64 candleCount;
        QByteArray packedBytes;
    };

    bool rejectSnapshot(const QString& errorMessage);

    std::atomic<std::shared_ptr<const Snapshot>> pendingSnapshot_;
    std::shared_ptr<const Snapshot> renderSnapshot_;
    quint64 latestRevision_ = 0;
    quint64 candleCount_ = 0;
    QString lastSnapshotError_;
};
