from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_formatter import (
    format_exchange_connection_status,
)


def _success_status(**overrides) -> ExchangeConnectionStatus:
    defaults = {
        "venue": TradingVenue.FUTURES_TESTNET,
        "reachable": True,
        "failure": None,
        "server_time_skew_ms": 134,
        "usdt_balance": Decimal("15000.00"),
        "position_mode": PositionMode.ONE_WAY,
        "margin_type": MarginType.CROSSED,
        "open_position_count": 0,
    }
    defaults.update(overrides)
    return ExchangeConnectionStatus(**defaults)


def test_a_successful_check_shows_every_field():
    text = format_exchange_connection_status(_success_status())

    assert "FUTURES_TESTNET" in text
    assert "✔" in text
    assert "+134 ms" in text
    assert "an toàn" in text
    assert "ONE_WAY" in text
    assert "CROSSED" in text
    assert "15,000.00" in text


def test_a_clock_skew_beyond_the_recv_window_warns_instead_of_saying_safe():
    text = format_exchange_connection_status(_success_status(server_time_skew_ms=6000))

    assert "CẢNH BÁO" in text
    assert "an toàn" not in text


def test_an_unreachable_status_shows_the_failure_kind_and_guidance():
    status = ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=False,
        failure=ConnectionFailureKind.KEY_EXPIRED,
        server_time_skew_ms=None,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
    )

    text = format_exchange_connection_status(status)

    assert "✘" in text
    assert "KEY_EXPIRED" in text
    assert "testnet.binancefuture.com" in text


def test_every_failure_kind_has_guidance_text():
    """A `ConnectionFailureKind` added without matching guidance would
    KeyError at render time — this catches that at test time instead."""
    for kind in ConnectionFailureKind:
        status = ExchangeConnectionStatus(
            venue=TradingVenue.FUTURES_TESTNET,
            reachable=False,
            failure=kind,
            server_time_skew_ms=None,
            usdt_balance=None,
            position_mode=None,
            margin_type=None,
            open_position_count=None,
        )
        text = format_exchange_connection_status(status)
        assert kind.name in text


def test_hedge_mode_shows_reachable_but_still_names_the_failure():
    """§2.3 — reachable and Hedge Mode are not mutually exclusive; the
    account connected fine, it just can't trade here."""
    status = _success_status(
        position_mode=PositionMode.HEDGE,
        failure=ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED,
    )

    text = format_exchange_connection_status(status)

    assert "✔" in text
    assert "HEDGE_MODE_UNSUPPORTED" in text
    assert "Hedge Mode" in text
