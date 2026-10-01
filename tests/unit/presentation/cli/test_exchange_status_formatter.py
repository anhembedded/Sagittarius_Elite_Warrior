from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AssetMode,
    FuturesAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_formatter import (
    format_exchange_connection_status,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
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
    assert "safe" in text
    assert "ONE_WAY" in text
    assert "CROSSED" in text
    assert "15,000.00" in text


def test_a_clock_skew_beyond_the_recv_window_warns_instead_of_saying_safe():
    text = format_exchange_connection_status(_success_status(server_time_skew_ms=6000))

    assert "WARNING" in text
    assert "safe" not in text


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


def _spot_holding(asset: str, free: str, locked: str = "0") -> SpotHolding:
    return SpotHolding(
        asset=asset,
        free=Decimal(free),
        locked=Decimal(locked),
        dust_threshold=Decimal("0.00000001"),
    )


def _spot_success_status(**overrides) -> ExchangeConnectionStatus:
    defaults = {
        "venue": TradingVenue.SPOT_TESTNET,
        "reachable": True,
        "failure": None,
        "server_time_skew_ms": 50,
        "usdt_balance": Decimal("10000.00"),
        "position_mode": None,
        "margin_type": None,
        "open_position_count": None,
        "holdings": (
            _spot_holding("USDT", "10000.00"),
            _spot_holding("BTC", "0.5"),
        ),
        "equity": Decimal("35000.00"),
    }
    defaults.update(overrides)
    return ExchangeConnectionStatus(**defaults)


def test_a_spot_success_shows_holdings_and_equity_not_position_mode():
    """`EPIC-027H` — `holdings is not None` is what routes rendering to the
    Spot shape; Spot has no position mode/margin type to show."""
    text = format_exchange_connection_status(_spot_success_status())

    assert "SPOT_TESTNET" in text
    assert "BTC" in text
    assert "35,000.00" in text
    assert "Position mode" not in text
    assert "Margin type" not in text


def test_a_spot_success_omits_the_quote_asset_from_the_holdings_list():
    text = format_exchange_connection_status(_spot_success_status())

    holdings_section = text.split("Holdings:", 1)[1]
    assert "USDT" not in holdings_section


def test_a_spot_success_with_no_holdings_says_so_rather_than_an_empty_list():
    text = format_exchange_connection_status(
        _spot_success_status(holdings=(_spot_holding("USDT", "10000.00"),))
    )

    assert "none above dust threshold" in text


def test_unavailable_spot_equity_shows_a_question_mark_never_a_guess():
    """`SpotAccountReader._compute_equity` returns `None` rather than a
    partial sum when a holding could not be priced (`EPIC-027H`) — the
    formatter must show that as "not available", not silently omit the
    line or print `0.00`."""
    text = format_exchange_connection_status(_spot_success_status(equity=None))

    lines = [line for line in text.splitlines() if "Equity" in line]
    assert len(lines) == 1
    assert "?" in lines[0]


def test_a_spot_key_mixup_gets_spot_specific_guidance():
    status = ExchangeConnectionStatus(
        venue=TradingVenue.SPOT_TESTNET,
        reachable=False,
        failure=ConnectionFailureKind.KEY_EXPIRED,
        server_time_skew_ms=None,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
    )

    text = format_exchange_connection_status(status)

    assert "testnet.binance.vision" in text
    assert "Futures Testnet keys" in text
    assert "testnet.binancefuture.com" not in text


def test_a_spot_not_configured_status_points_at_the_spot_env_vars():
    status = ExchangeConnectionStatus(
        venue=TradingVenue.SPOT_TESTNET,
        reachable=False,
        failure=ConnectionFailureKind.NOT_CONFIGURED,
        server_time_skew_ms=None,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
    )

    text = format_exchange_connection_status(status)

    assert "BINANCE_SPOT_TESTNET_API_KEY" in text


def test_a_spot_clock_skew_failure_reuses_the_venue_agnostic_guidance():
    """`CLOCK_SKEW` has no Spot-specific entry — `_guidance_for` must fall
    back to the shared table rather than raising a `KeyError`."""
    status = ExchangeConnectionStatus(
        venue=TradingVenue.SPOT_TESTNET,
        reachable=False,
        failure=ConnectionFailureKind.CLOCK_SKEW,
        server_time_skew_ms=None,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
    )

    text = format_exchange_connection_status(status)

    assert "Resync the system" in text


# --- EPIC-028D — what a new Futures order can spend ---------------------------


def test_a_futures_success_shows_available_apart_from_the_wallet():
    summary = FuturesAccountSummary(
        venue=TradingVenue.FUTURES_TESTNET,
        available_balance=Decimal("11874.50"),
        equity=Decimal("14874.50"),
        wallet_balance=Decimal("15000.00"),
        margin_balance=Decimal("14874.50"),
        unrealized_pnl=Decimal("-125.50"),
        position_mode=PositionMode.ONE_WAY,
    )

    text = format_exchange_connection_status(_success_status(summary=summary))

    assert "Available (USDT): 11,874.50" in text
    assert "Unrealized PnL: -125.50" in text
    assert "Wallet (USDT):    15,000.00" in text


def test_a_multi_assets_futures_success_names_the_margin_its_available_counts():
    """`EPIC-028O` — a Multi-Assets figure is every margin asset in USD, so
    it is never labelled USDT."""
    summary = FuturesAccountSummary(
        venue=TradingVenue.FUTURES_TESTNET,
        available_balance=Decimal("15084.90"),
        equity=Decimal("18084.90"),
        wallet_balance=Decimal("18210.40"),
        margin_balance=Decimal("18084.90"),
        unrealized_pnl=Decimal("-125.50"),
        position_mode=PositionMode.ONE_WAY,
        asset_mode=AssetMode.MULTI_ASSETS,
    )

    text = format_exchange_connection_status(_success_status(summary=summary))

    assert "Available (USD, all assets): 15,084.90" in text
    assert "Available (USDT)" not in text


def test_a_futures_success_without_a_summary_shows_a_question_mark_not_zero():
    text = format_exchange_connection_status(_success_status())

    assert "Available (USDT): ?" in text
    assert "Unrealized PnL: ?" in text
