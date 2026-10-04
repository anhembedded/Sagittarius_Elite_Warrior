"""`BUG-147` — a bot's `ExchangeTerms` carry the venue's price band, so the
Grid's band check sees what trading's rules publish."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_exchange_terms import (
    exchange_terms_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    PriceBand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    PercentPriceBand,
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)

_CAPS = OwnerBudgetCaps(40, timedelta(0), 30)


def _terms(band: PercentPriceBand | None) -> FakeOrderEntryTerms:
    rules = SymbolOrderMetadata(
        symbol="BTCUSDT",
        status="TRADING",
        step_size=Decimal("0.00001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(5),
        quantity_precision=None,
        price_precision=None,
        fetched_at=datetime(2026, 10, 4, tzinfo=UTC),
        price_band=band,
    )
    commission = CommissionRate(
        symbol="BTCUSDT", maker=Decimal("0.001"), taker=Decimal("0.001")
    )
    return FakeOrderEntryTerms(OrderEntryTerms(rules, commission))


def test_the_venues_band_reaches_the_bots_terms() -> None:
    band = PercentPriceBand(
        bid_down=Decimal("0.2"),
        bid_up=Decimal(5),
        ask_down=Decimal("0.3"),
        ask_up=Decimal(4),
    )

    terms = exchange_terms_for(_terms(band), "BTCUSDT", _CAPS)

    assert terms.price_band == PriceBand(
        buy_down=Decimal("0.2"),
        buy_up=Decimal(5),
        sell_down=Decimal("0.3"),
        sell_up=Decimal(4),
    )


def test_no_band_published_means_none() -> None:
    assert exchange_terms_for(_terms(None), "BTCUSDT", _CAPS).price_band is None
