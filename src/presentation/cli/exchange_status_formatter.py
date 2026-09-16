"""Renders `ExchangeConnectionStatus` as the two-shape text `EPIC-021D` §5
specifies — a success table, or a one-line failure plus guidance. Shared by
the headless (`exchange_status_cmd.py`) and interactive
(`ExchangeStatusCliHandler`) CLI entry points, so the two never drift."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

#: python-binance's own default `recvWindow` — matches what
#: `FuturesSessionFactory.create_trading_client()` implicitly uses (no
#: override is passed), so this is the real threshold a request would be
#: judged against, not an arbitrary display cutoff.
_RECV_WINDOW_MS = 5000

_FAILURE_GUIDANCE = EnumLabels(
    ConnectionFailureKind,
    {
        ConnectionFailureKind.NOT_CONFIGURED: (
            "API key/secret not configured. Get a key at testnet.binancefuture.com, "
            "then save it via the Settings screen or the "
            "BINANCE_FUTURES_TESTNET_API_KEY/BINANCE_FUTURES_TESTNET_API_SECRET "
            "environment variables."
        ),
        ConnectionFailureKind.BAD_SIGNATURE: (
            "Request signature is invalid. Double-check the API Secret was "
            "copied correctly, with no extra or missing characters."
        ),
        ConnectionFailureKind.CLOCK_SKEW: (
            "The local clock is too far from the exchange's time. Resync the system "
            "clock (NTP) and try again."
        ),
        ConnectionFailureKind.KEY_EXPIRED: (
            "The testnet key has expired or been reset. Get a new key at "
            "testnet.binancefuture.com.\n"
            "  (Note: Spot Testnet keys and mainnet keys do NOT work here.)"
        ),
        ConnectionFailureKind.NETWORK: (
            "Could not connect to the exchange. Check your network/proxy and try again."
        ),
        ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED: (
            "The account is in Hedge Mode. This epic assumes One-way Mode — "
            "switch it back under Binance Futures > Settings > Position Mode "
            "on the Binance web/app, then check the connection again."
        ),
    },
)


def _require_failure_kind(status: ExchangeConnectionStatus) -> ConnectionFailureKind:
    """Both failure-rendering branches are only ever reached when
    `status.failure is not None` (see `format_exchange_connection_status`'s
    own branching) — this turns that invariant into a real `ValueError`
    instead of an `assert`, which is stripped under `-O` and would let a
    violated invariant silently fall through to a `None.name` crash."""
    if status.failure is None:
        raise ValueError("Expected a failure kind on a non-success status.")
    return status.failure


def format_exchange_connection_status(status: ExchangeConnectionStatus) -> str:
    if status.failure is not None and not status.reachable:
        return _format_unreachable(status)
    if status.failure is not None:
        return _format_reachable_with_failure(status)
    return _format_success(status)


def _format_unreachable(status: ExchangeConnectionStatus) -> str:
    kind = _require_failure_kind(status)
    lines = [f"Venue: {status.venue.name}   Connection: ✘  {kind.name}"]
    lines.append(f"→ {_FAILURE_GUIDANCE[kind]}")
    return "\n".join(lines)


def _format_reachable_with_failure(status: ExchangeConnectionStatus) -> str:
    """Reachable, but a later check (Hedge Mode) blocks trade-readiness —
    show what was actually learned, then the guidance."""
    kind = _require_failure_kind(status)
    lines = [f"Venue: {status.venue.name}   Connection: ✔  but {kind.name}"]
    if status.usdt_balance is not None:
        lines.append(f"USDT balance: {status.usdt_balance:,.2f}")
    lines.append(f"→ {_FAILURE_GUIDANCE[kind]}")
    return "\n".join(lines)


def _format_success(status: ExchangeConnectionStatus) -> str:
    skew = status.server_time_skew_ms
    skew_text = "?" if skew is None else f"{skew:+d} ms"
    skew_safety = (
        ""
        if skew is None
        else (
            f"(recvWindow {_RECV_WINDOW_MS} ms → safe)"
            if abs(skew) < _RECV_WINDOW_MS
            else f"(recvWindow {_RECV_WINDOW_MS} ms → WARNING, may hit -1021)"
        )
    )
    position_mode_text = (
        "?" if status.position_mode is None else f"{status.position_mode.name} ✔"
    )
    margin_type_text = "?" if status.margin_type is None else status.margin_type.name
    balance_text = "?" if status.usdt_balance is None else f"{status.usdt_balance:,.2f}"
    open_positions_text = (
        "?" if status.open_position_count is None else str(status.open_position_count)
    )

    return "\n".join(
        [
            f"Venue:            {status.venue.name:<25} Connection: ✔",
            f"Clock skew:       {skew_text:<25} {skew_safety}",
            f"Position mode:    {position_mode_text:<25} Margin type: {margin_type_text}",
            f"USDT balance:     {balance_text:<25} Open positions: {open_positions_text}",
        ]
    )
