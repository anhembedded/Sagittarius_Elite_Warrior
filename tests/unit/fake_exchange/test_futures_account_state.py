"""`EPIC-028O` — the fake Futures account's position and wallet rules, at
prices a test chooses: the volume-weighted entry, realized PnL on a partial
close and on a flip, and the fee on every fill. The HTTP round trip through
the real adapters is `test_futures_fills_against_fake_server.py`."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "sanity"))
from fake_exchange.futures_account_state import FuturesAccountState
from fake_exchange.futures_symbol_config import FuturesSymbolConfig


def _account() -> FuturesAccountState:
    return FuturesAccountState(FuturesSymbolConfig())


def _position(account: FuturesAccountState) -> tuple[str, str]:
    (row,) = account.position_risk("BTCUSDT")
    return row["positionAmt"], row["entryPrice"]


def test_adding_to_a_long_weights_the_entry_by_quantity() -> None:
    account = _account()
    account.fill_at("BTCUSDT", "BUY", Decimal(1), Decimal(60000))
    account.fill_at("BTCUSDT", "BUY", Decimal(3), Decimal(64000))

    # (1 × 60 000 + 3 × 64 000) ÷ 4 = 63 000
    assert _position(account) == ("4.00000000", "63000.00000000")


def test_a_partial_close_realizes_its_share_and_keeps_the_entry() -> None:
    account = _account()
    account.fill_at("BTCUSDT", "BUY", Decimal(2), Decimal(60000))

    fill = account.fill_at("BTCUSDT", "SELL", Decimal(1), Decimal(61000))

    # (61 000 − 60 000) × 1
    assert fill.realized_pnl == Decimal(1000)
    assert _position(account) == ("1.00000000", "60000.00000000")


def test_closing_a_short_above_its_entry_loses() -> None:
    account = _account()
    account.fill_at("BTCUSDT", "SELL", Decimal(1), Decimal(60000))

    fill = account.fill_at("BTCUSDT", "BUY", Decimal(1), Decimal(61000))

    assert fill.realized_pnl == Decimal(-1000)
    assert account.position_risk("BTCUSDT") == []


def test_a_fill_past_zero_opens_the_rest_the_other_way_at_the_fill_price() -> None:
    account = _account()
    account.fill_at("BTCUSDT", "BUY", Decimal(1), Decimal(60000))

    fill = account.fill_at("BTCUSDT", "SELL", Decimal(3), Decimal(62000))

    assert fill.realized_pnl == Decimal(2000)
    assert _position(account) == ("-2.00000000", "62000.00000000")


def test_every_fill_pays_the_taker_fee_and_pnl_lands_in_the_wallet() -> None:
    account = _account()
    account.fill_at("BTCUSDT", "BUY", Decimal(1), Decimal(60000))
    account.fill_at("BTCUSDT", "SELL", Decimal(1), Decimal(61000))

    # 15 000 − 60 000 × 0.05 % − 61 000 × 0.05 % + 1 000
    assert account.account()["totalWalletBalance"] == "15939.50000000"


def test_a_shorts_notional_is_signed_as_binance_sends_it() -> None:
    account = _account()
    account.fill_at("BTCUSDT", "SELL", Decimal(1), Decimal(60000))

    (row,) = account.position_risk("BTCUSDT")

    # −1 × the 64 000.0 mark; initial margin stays positive (20x default).
    assert row["notional"] == "-64000.00000000"
    assert row["initialMargin"] == "3200.00000000"
