from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from enum import StrEnum

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.audit_database_integrity.query import (
    AuditDatabaseIntegrityQuery,
    DataAnomalyDTO,
    DatabaseAuditResultDTO,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData


class AnomalyType(StrEnum):
    """
    @brief The kinds of defect this audit can report.

    @details A `StrEnum` rather than bare strings: the value reaches the UI and
    the DTO as text either way, but naming them here means adding a rule cannot
    silently invent a spelling, and a typo becomes an import error instead of an
    anomaly nobody matches on.
    """

    NON_FINITE_VALUE = "NON_FINITE_VALUE"
    NON_POSITIVE_PRICE = "NON_POSITIVE_PRICE"
    NEGATIVE_VOLUME = "NEGATIVE_VOLUME"
    HIGH_LESS_THAN_LOW = "HIGH_LESS_THAN_LOW"
    HIGH_NOT_MAXIMUM = "HIGH_NOT_MAXIMUM"
    LOW_NOT_MINIMUM = "LOW_NOT_MINIMUM"
    DUPLICATE_TIMESTAMP = "DUPLICATE_TIMESTAMP"


#: One candle's numbers, captured once and attached to every anomaly it raises.
#: Annotated rather than inferred: `dict` is invariant, so a `dict[str, float]`
#: cannot be passed where `dict[str, float | str]` is expected, and inference
#: produced exactly that mismatch at every construction site.
RawValues = dict[str, float | str]

#: A rule that inspects one candle in isolation and either names a defect or
#: stays silent. Stateless by construction — the two rules that are not
#: (non-finite short-circuits the rest, duplicate-timestamp needs history) are
#: deliberately kept out of this table and handled explicitly in the loop.
AnomalyRule = Callable[[MarketData, RawValues], DataAnomalyDTO | None]


def _raw_values(kline: MarketData) -> RawValues:
    return {
        "open": kline.open_price,
        "high": kline.high_price,
        "low": kline.low_price,
        "close": kline.close_price,
        "volume": kline.volume,
        "trades": kline.number_of_trades,
    }


def _prices(kline: MarketData) -> list[float]:
    return [
        kline.open_price,
        kline.high_price,
        kline.low_price,
        kline.close_price,
    ]


def _check_non_finite(kline: MarketData, raw: RawValues) -> DataAnomalyDTO | None:
    if any(not math.isfinite(p) for p in _prices(kline)) or not math.isfinite(
        kline.volume
    ):
        return DataAnomalyDTO(
            timestamp=kline.open_time,
            anomaly_type=AnomalyType.NON_FINITE_VALUE,
            description="KLine contains NaN or Infinite numeric values.",
            raw_values=raw,
        )
    return None


def _check_non_positive_price(
    kline: MarketData, raw: RawValues
) -> DataAnomalyDTO | None:
    if any(p <= 0 for p in _prices(kline)):
        return DataAnomalyDTO(
            timestamp=kline.open_time,
            anomaly_type=AnomalyType.NON_POSITIVE_PRICE,
            description="Price must be strictly positive (> 0).",
            raw_values=raw,
        )
    return None


def _check_negative_volume(kline: MarketData, raw: RawValues) -> DataAnomalyDTO | None:
    if kline.volume < 0:
        return DataAnomalyDTO(
            timestamp=kline.open_time,
            anomaly_type=AnomalyType.NEGATIVE_VOLUME,
            description=f"Volume cannot be negative (found {kline.volume}).",
            raw_values=raw,
        )
    return None


def _check_high_below_low(kline: MarketData, raw: RawValues) -> DataAnomalyDTO | None:
    if kline.high_price < kline.low_price:
        return DataAnomalyDTO(
            timestamp=kline.open_time,
            anomaly_type=AnomalyType.HIGH_LESS_THAN_LOW,
            description=f"High ({kline.high_price}) is lower than Low ({kline.low_price}).",
            raw_values=raw,
        )
    return None


def _check_high_not_maximum(kline: MarketData, raw: RawValues) -> DataAnomalyDTO | None:
    if kline.high_price < kline.open_price or kline.high_price < kline.close_price:
        return DataAnomalyDTO(
            timestamp=kline.open_time,
            anomaly_type=AnomalyType.HIGH_NOT_MAXIMUM,
            description=f"High ({kline.high_price}) is not the maximum among Open/Close.",
            raw_values=raw,
        )
    return None


def _check_low_not_minimum(kline: MarketData, raw: RawValues) -> DataAnomalyDTO | None:
    if kline.low_price > kline.open_price or kline.low_price > kline.close_price:
        return DataAnomalyDTO(
            timestamp=kline.open_time,
            anomaly_type=AnomalyType.LOW_NOT_MINIMUM,
            description=f"Low ({kline.low_price}) is not the minimum among Open/Close.",
            raw_values=raw,
        )
    return None


#: Evaluated in order, and every rule that fires contributes an anomaly — a
#: candle can break several of these at once. Order is the reported order.
_VALUE_RULES: tuple[AnomalyRule, ...] = (
    _check_non_positive_price,
    _check_negative_volume,
    _check_high_below_low,
    _check_high_not_maximum,
    _check_low_not_minimum,
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
        # Fetch all candles ordered chronologically
        klines = self._repository.get_klines(
            symbol=query.symbol,
            interval=query.interval,
            limit=None,
            order_by_desc=False,
        )
        anomalies = self._collect_anomalies(klines)

        return DatabaseAuditResultDTO(
            symbol=query.symbol,
            interval=query.interval.value,
            total_checked=len(klines),
            is_clean=len(anomalies) == 0,
            anomaly_count=len(anomalies),
            anomalies=anomalies,
        )

    def _collect_anomalies(self, klines: Iterable[MarketData]) -> list[DataAnomalyDTO]:
        anomalies: list[DataAnomalyDTO] = []
        seen_timestamps: set[float] = set()

        for kline in klines:
            raw = _raw_values(kline)

            # A candle whose numbers are not finite cannot be compared against
            # anything, so it reports once and the remaining rules are skipped.
            # Note the consequence, which predates this decomposition and is
            # preserved deliberately: such a candle never enters
            # `seen_timestamps`, so its timestamp cannot make a later candle
            # look like a duplicate.
            non_finite = _check_non_finite(kline, raw)
            if non_finite is not None:
                anomalies.append(non_finite)
                continue

            for rule in _VALUE_RULES:
                anomaly = rule(kline, raw)
                if anomaly is not None:
                    anomalies.append(anomaly)

            duplicate = self._check_duplicate_timestamp(kline, raw, seen_timestamps)
            if duplicate is not None:
                anomalies.append(duplicate)

        return anomalies

    @staticmethod
    def _check_duplicate_timestamp(
        kline: MarketData, raw: RawValues, seen_timestamps: set[float]
    ) -> DataAnomalyDTO | None:
        """The one rule that needs history, so it owns the set it reads."""
        ts_epoch = kline.open_time.timestamp()
        if ts_epoch in seen_timestamps:
            return DataAnomalyDTO(
                timestamp=kline.open_time,
                anomaly_type=AnomalyType.DUPLICATE_TIMESTAMP,
                description=f"Duplicate candle timestamp found at {kline.open_time.isoformat()}.",
                raw_values=raw,
            )
        seen_timestamps.add(ts_epoch)
        return None
