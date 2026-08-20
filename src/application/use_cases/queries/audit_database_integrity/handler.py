from __future__ import annotations

import math
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.audit_database_integrity.query import (
    AuditDatabaseIntegrityQuery,
    DataAnomalyDTO,
    DatabaseAuditResultDTO,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
        IMarketDataRepository,
    )


class AuditDatabaseIntegrityQueryHandler(
    IQueryHandler[AuditDatabaseIntegrityQuery, DatabaseAuditResultDTO]
):
    """
    @brief Handler that performs comprehensive data integrity auditing on historical klines.
    """

    def __init__(self, repository: IMarketDataRepository) -> None:
        self._repository = repository

    def execute(self, query: AuditDatabaseIntegrityQuery) -> DatabaseAuditResultDTO:
        interval_vo = TimeFrame(query.interval)
        # Fetch all candles ordered chronologically
        klines = self._repository.get_klines(
            symbol=query.symbol,
            interval=interval_vo,
            limit=None,
            order_by_desc=False,
        )

        anomalies: list[DataAnomalyDTO] = []
        seen_timestamps: set[float] = set()

        for kline in klines:
            raw = {
                "open": kline.open_price,
                "high": kline.high_price,
                "low": kline.low_price,
                "close": kline.close_price,
                "volume": kline.volume,
                "trades": kline.number_of_trades,
            }

            # 1. Non-finite / NaN / Inf validation
            prices = [
                kline.open_price,
                kline.high_price,
                kline.low_price,
                kline.close_price,
            ]
            if any(not math.isfinite(p) for p in prices) or not math.isfinite(
                kline.volume
            ):
                anomalies.append(
                    DataAnomalyDTO(
                        timestamp=kline.open_time,
                        anomaly_type="NON_FINITE_VALUE",
                        description="KLine contains NaN or Infinite numeric values.",
                        raw_values=raw,
                    )
                )
                continue

            # 2. Non-positive price or negative volume validation
            if any(p <= 0 for p in prices):
                anomalies.append(
                    DataAnomalyDTO(
                        timestamp=kline.open_time,
                        anomaly_type="NON_POSITIVE_PRICE",
                        description="Price must be strictly positive (> 0).",
                        raw_values=raw,
                    )
                )

            if kline.volume < 0:
                anomalies.append(
                    DataAnomalyDTO(
                        timestamp=kline.open_time,
                        anomaly_type="NEGATIVE_VOLUME",
                        description=f"Volume cannot be negative (found {kline.volume}).",
                        raw_values=raw,
                    )
                )

            # 3. High / Low extrema inversion checks
            if kline.high_price < kline.low_price:
                anomalies.append(
                    DataAnomalyDTO(
                        timestamp=kline.open_time,
                        anomaly_type="HIGH_LESS_THAN_LOW",
                        description=f"High ({kline.high_price}) is lower than Low ({kline.low_price}).",
                        raw_values=raw,
                    )
                )

            if (
                kline.high_price < kline.open_price
                or kline.high_price < kline.close_price
            ):
                anomalies.append(
                    DataAnomalyDTO(
                        timestamp=kline.open_time,
                        anomaly_type="HIGH_NOT_MAXIMUM",
                        description=f"High ({kline.high_price}) is not the maximum among Open/Close.",
                        raw_values=raw,
                    )
                )

            if (
                kline.low_price > kline.open_price
                or kline.low_price > kline.close_price
            ):
                anomalies.append(
                    DataAnomalyDTO(
                        timestamp=kline.open_time,
                        anomaly_type="LOW_NOT_MINIMUM",
                        description=f"Low ({kline.low_price}) is not the minimum among Open/Close.",
                        raw_values=raw,
                    )
                )

            # 4. Duplicate timestamp check
            ts_epoch = kline.open_time.timestamp()
            if ts_epoch in seen_timestamps:
                anomalies.append(
                    DataAnomalyDTO(
                        timestamp=kline.open_time,
                        anomaly_type="DUPLICATE_TIMESTAMP",
                        description=f"Duplicate candle timestamp found at {kline.open_time.isoformat()}.",
                        raw_values=raw,
                    )
                )
            else:
                seen_timestamps.add(ts_epoch)

        return DatabaseAuditResultDTO(
            symbol=query.symbol,
            interval=query.interval,
            total_checked=len(klines),
            is_clean=len(anomalies) == 0,
            anomaly_count=len(anomalies),
            anomalies=anomalies,
        )
