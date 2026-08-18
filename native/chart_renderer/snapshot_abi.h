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

inline constexpr char IndicatorMagic[4] = {'S', 'G', 'I', 'N'};
inline constexpr quint16 IndicatorVersion = 1;
inline constexpr quint16 IndicatorHeaderBytes = 32;
// Indicator snapshot v1 is little-endian and structure-of-arrays:
// magic[4], version:u16, headerBytes:u16, revision:u64, candleCount:u64,
// seriesCount:u32, reserved:u32, rgba:u32[seriesCount],
// values:f64[candleCount] for each series in color-plane order.

inline constexpr char MarkerMagic[4] = {'S', 'G', 'M', 'K'};
inline constexpr quint16 MarkerVersion = 1;
inline constexpr quint16 MarkerHeaderBytes = 32;
inline constexpr quint64 MarkerRecordBytes = 24;
// Marker snapshot v1 is little-endian and array-of-structures:
// magic[4], version:u16, headerBytes:u16, revision:u64, candleCount:u64,
// markerCount:u64, then records:
// candleIndex:u64, price:f64, rgba:u32, kind:u8, direction:u8, reserved:u16.
// kind: 1=LONG_ENTRY, 2=LONG_EXIT, 3=SHORT_ENTRY, 4=SHORT_EXIT.
// direction: 1=UP, 2=DOWN.

}  // namespace Sagittarius::NativeChart::SnapshotAbi
