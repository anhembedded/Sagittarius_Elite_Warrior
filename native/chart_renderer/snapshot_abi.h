#pragma once

#include <QtGlobal>

namespace Sagittarius::NativeChart::SnapshotAbi {

inline constexpr char Magic[4] = {'S', 'G', 'C', 'H'};
inline constexpr quint16 Version = 1;
inline constexpr quint16 HeaderBytes = 24;
inline constexpr quint64 BytesPerCandle = 48;

// Snapshot v1 is little-endian and structure-of-arrays:
// magic[4], version:u16, headerBytes:u16, revision:u64, candleCount:u64,
// timestampsUtcMs:i64[count] (strictly increasing Unix epoch milliseconds),
// then open/high/low/close/volume:f64[count].

}  // namespace Sagittarius::NativeChart::SnapshotAbi
