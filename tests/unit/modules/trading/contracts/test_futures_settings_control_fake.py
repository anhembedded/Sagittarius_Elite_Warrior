"""`EPIC-028I` — `FakeFuturesSettingsControl` applies what it is asked, or
answers the refusal a test arranged (`BUG-120`)."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_result import (
    AccountControlRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_futures_settings_control import (
    FakeFuturesSettingsControl,
)


def test_a_change_is_applied_and_recorded() -> None:
    fake = FakeFuturesSettingsControl(max_notional=Decimal(5000))

    leverage = fake.change_leverage("BTCUSDT", 20)
    margin = fake.change_margin_type("BTCUSDT", MarginType.ISOLATED)

    assert leverage.applied is not None
    assert (leverage.applied.leverage, leverage.applied.max_notional) == (
        20,
        Decimal(5000),
    )
    assert margin.applied is MarginType.ISOLATED
    assert fake.leverage_changes == [("BTCUSDT", 20)]
    assert fake.margin_changes == [("BTCUSDT", MarginType.ISOLATED)]


def test_an_arranged_refusal_is_answered_for_both() -> None:
    fake = FakeFuturesSettingsControl()
    fake.refuses_with(AccountControlRefusal.POSITION_OPEN, "BTCUSDT has a position")

    for result in (
        fake.change_leverage("BTCUSDT", 3),
        fake.change_margin_type("BTCUSDT", MarginType.CROSSED),
    ):
        assert result.blocked_by is AccountControlRefusal.POSITION_OPEN
        assert result.detail == "BTCUSDT has a position"
