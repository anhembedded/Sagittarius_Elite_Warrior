"""Pure domain entities and order rule validation for symbol market metadata (BOT-095E1)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

_DEFAULT_METADATA_MAX_AGE_SECONDS = 86400.0  # 24 hours


class MetadataVerificationStatus(str, Enum):
    """Observable verification state for symbol order rules."""

    VERIFIED = "VERIFIED"
    UNVERIFIED_MISSING = "UNVERIFIED_MISSING"
    UNVERIFIED_STALE = "UNVERIFIED_STALE"


@dataclass(frozen=True)
class PriceFilter:
    """Price bounds and precision tick size for a symbol."""

    min_price: float
    max_price: float
    tick_size: float

    def validate_price(self, price: float) -> str | None:
        if not math.isfinite(price) or price <= 0:
            return "Giá đặt lệnh phải là số dương hữu hạn."
        if price < self.min_price:
            return f"Giá {price:,.4f} nhỏ hơn giá tối thiểu cho phép ({self.min_price:,.4f})."
        if price > self.max_price:
            return f"Giá {price:,.4f} vượt quá giá tối đa cho phép ({self.max_price:,.4f})."
        if self.tick_size > 0:
            steps = round((price - self.min_price) / self.tick_size)
            expected_price = self.min_price + steps * self.tick_size
            if not math.isclose(price, expected_price, abs_tol=1e-8):
                return f"Giá {price:,.8f} không khớp bước giá tick size ({self.tick_size:,.8f})."
        return None


@dataclass(frozen=True)
class LotSizeFilter:
    """Quantity bounds and step size for a symbol."""

    min_qty: float
    max_qty: float
    step_size: float

    def validate_quantity(self, quantity: float) -> str | None:
        if not math.isfinite(quantity) or quantity <= 0:
            return "Khối lượng đặt lệnh phải là số dương hữu hạn."
        if quantity < self.min_qty:
            return f"Khối lượng {quantity:,.4f} nhỏ hơn khối lượng tối thiểu ({self.min_qty:,.4f})."
        if quantity > self.max_qty:
            return f"Khối lượng {quantity:,.4f} vượt quá khối lượng tối đa ({self.max_qty:,.4f})."
        if self.step_size > 0:
            steps = round((quantity - self.min_qty) / self.step_size)
            expected_qty = self.min_qty + steps * self.step_size
            if not math.isclose(quantity, expected_qty, abs_tol=1e-8):
                return f"Khối lượng {quantity:,.8f} không khớp bước nhảy lot size ({self.step_size:,.8f})."
        return None


@dataclass(frozen=True)
class NotionalFilter:
    """Minimum order notional value (price * quantity) requirement."""

    min_notional: float
    apply_to_market: bool = True

    def validate_notional(self, notional: float) -> str | None:
        if not math.isfinite(notional) or notional <= 0:
            return "Giá trị danh nghĩa (notional) phải là số dương hữu hạn."
        if notional < self.min_notional:
            return (
                f"Giá trị lệnh {notional:,.2f} nhỏ hơn giá trị tối thiểu sàn yêu cầu "
                f"({self.min_notional:,.2f})."
            )
        return None


@dataclass(frozen=True)
class SymbolMarketMetadata:
    """Immutable snapshot of symbol metadata and trading filters from an exchange."""

    symbol: str
    status: str
    base_asset: str
    quote_asset: str
    price_filter: PriceFilter
    lot_size_filter: LotSizeFilter
    notional_filter: NotionalFilter
    fetched_at: datetime

    def is_stale(
        self,
        max_age_seconds: float = _DEFAULT_METADATA_MAX_AGE_SECONDS,
        now: datetime | None = None,
    ) -> bool:
        current_time = now or datetime.now(UTC)
        age = (current_time - self.fetched_at).total_seconds()
        return age > max_age_seconds


@dataclass(frozen=True)
class OrderIntent:
    """Specific order calculation intent to validate against market rules."""

    symbol: str
    price: float
    quantity: float
    order_type: str = "LIMIT"

    @property
    def notional(self) -> float:
        return self.price * self.quantity


@dataclass(frozen=True)
class OrderIntentValidationResult:
    """Result of validating an order intent against cached exchange filters."""

    status: MetadataVerificationStatus
    is_valid: bool
    issues: tuple[str, ...]
    metadata: SymbolMarketMetadata | None
    explanation: str


def validate_order_intent(
    intent: OrderIntent,
    metadata: SymbolMarketMetadata | None,
    *,
    max_age_seconds: float = _DEFAULT_METADATA_MAX_AGE_SECONDS,
    now: datetime | None = None,
) -> OrderIntentValidationResult:
    """Validates an order intent truthfully against cached market metadata."""
    if metadata is None:
        return OrderIntentValidationResult(
            status=MetadataVerificationStatus.UNVERIFIED_MISSING,
            is_valid=True,
            issues=(),
            metadata=None,
            explanation="Chưa xác minh theo quy tắc sàn (chưa có metadata cho cặp giao dịch).",
        )

    if metadata.is_stale(max_age_seconds=max_age_seconds, now=now):
        return OrderIntentValidationResult(
            status=MetadataVerificationStatus.UNVERIFIED_STALE,
            is_valid=True,
            issues=(),
            metadata=metadata,
            explanation=(
                f"Chưa xác minh theo quy tắc sàn (metadata đã cũ, lấy từ "
                f"{metadata.fetched_at.strftime('%Y-%m-%d %H:%M:%S UTC')})."
            ),
        )

    issues: list[str] = []

    price_issue = metadata.price_filter.validate_price(intent.price)
    if price_issue:
        issues.append(price_issue)

    qty_issue = metadata.lot_size_filter.validate_quantity(intent.quantity)
    if qty_issue:
        issues.append(qty_issue)

    notional_issue = metadata.notional_filter.validate_notional(intent.notional)
    if notional_issue:
        issues.append(notional_issue)

    is_valid = len(issues) == 0
    if is_valid:
        explanation = (
            f"Đã xác minh theo quy tắc sàn Binance (Min notional: {metadata.notional_filter.min_notional} "
            f"{metadata.quote_asset}, Step: {metadata.lot_size_filter.step_size}, "
            f"Tick: {metadata.price_filter.tick_size})."
        )
    else:
        explanation = "Không đạt quy tắc đặt lệnh của sàn: " + "; ".join(issues)

    return OrderIntentValidationResult(
        status=MetadataVerificationStatus.VERIFIED,
        is_valid=is_valid,
        issues=tuple(issues),
        metadata=metadata,
        explanation=explanation,
    )
