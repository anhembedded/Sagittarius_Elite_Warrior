"""Renders `ExchangeConnectionStatus` as the two-shape text `EPIC-021D` §5
specifies — a success table, or a one-line failure plus guidance. Shared by
the headless (`exchange_status_cmd.py`) and interactive
(`ExchangeStatusCliHandler`) CLI entry points, so the two never drift."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AssetMode,
    FuturesAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
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

#: `EPIC-027H` — the two failure kinds where a Futures key mixup and a Spot
#: key mixup need different wording (a different key page, and the mirror
#: of Futures' own "wrong testnet family" warning). Deliberately a plain
#: dict, not an `EnumLabels`: it covers only the members whose guidance
#: differs by venue, so `EnumLabels`'s completeness check (every member
#: must have a label) would reject it outright. Every other kind's guidance
#: is venue-agnostic and stays in `_FAILURE_GUIDANCE` above.
_SPOT_ONLY_GUIDANCE: dict[ConnectionFailureKind, str] = {
    ConnectionFailureKind.NOT_CONFIGURED: (
        "API key/secret not configured. Get a key at testnet.binance.vision, "
        "then save it via the Settings screen or the "
        "BINANCE_SPOT_TESTNET_API_KEY/BINANCE_SPOT_TESTNET_API_SECRET "
        "environment variables."
    ),
    ConnectionFailureKind.KEY_EXPIRED: (
        "The testnet key has expired or been reset. Get a new key at "
        "testnet.binance.vision.\n"
        "  (Note: Futures Testnet keys and mainnet keys do NOT work here.)"
    ),
}


def _guidance_for(status: ExchangeConnectionStatus, kind: ConnectionFailureKind) -> str:
    if status.venue is TradingVenue.SPOT_TESTNET and kind in _SPOT_ONLY_GUIDANCE:
        return _SPOT_ONLY_GUIDANCE[kind]
    return _FAILURE_GUIDANCE[kind]


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
    lines.append(f"→ {_guidance_for(status, kind)}")
    return "\n".join(lines)


def _format_reachable_with_failure(status: ExchangeConnectionStatus) -> str:
    """Reachable, but a later check (Hedge Mode) blocks trade-readiness —
    show what was actually learned, then the guidance."""
    kind = _require_failure_kind(status)
    lines = [f"Venue: {status.venue.name}   Connection: ✔  but {kind.name}"]
    if status.usdt_balance is not None:
        lines.append(f"USDT balance: {status.usdt_balance:,.2f}")
    lines.append(f"→ {_guidance_for(status, kind)}")
    return "\n".join(lines)


def _format_success(status: ExchangeConnectionStatus) -> str:
    if status.venue is TradingVenue.SPOT_TESTNET:
        return _format_spot_success(status)

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
    # `EPIC-028D` — the wallet balance includes margin already committed;
    # what a new order can spend is the available balance.
    summary = status.summary
    futures = summary if isinstance(summary, FuturesAccountSummary) else None
    available_text = "?" if futures is None else f"{futures.available_balance:,.2f}"
    upnl_text = "?" if futures is None else f"{futures.unrealized_pnl:+,.2f}"
    # `EPIC-028O` — in Multi-Assets mode the figure counts every margin
    # asset, in USD; labelling it USDT would misstate it. The label keeps the
    # column width, and one more line names the mode (PR #304 review,
    # finding 6).
    multi_assets = futures is not None and futures.asset_mode is AssetMode.MULTI_ASSETS
    available_label = "Available (USD): " if multi_assets else "Available (USDT):"
    asset_mode_lines = (
        ["Asset mode:       MULTI_ASSETS (every margin asset, in USD)"]
        if multi_assets
        else []
    )

    return "\n".join(
        [
            f"Venue:            {status.venue.name:<25} Connection: ✔",
            f"Clock skew:       {skew_text:<25} {skew_safety}",
            f"Position mode:    {position_mode_text:<25} Margin type: {margin_type_text}",
            f"Wallet (USDT):    {balance_text:<25} Open positions: {open_positions_text}",
            f"{available_label} {available_text:<25} Unrealized PnL: {upnl_text}",
            *asset_mode_lines,
        ]
    )


def _format_spot_success(status: ExchangeConnectionStatus) -> str:
    """`EPIC-027H` — Spot has no position mode/margin type to show, and a
    list of per-asset holdings instead of one USDT wallet figure. `?` for
    `equity` means "not available" (`SpotAccountReader` never guesses a
    partial sum), never a silently-omitted line."""
    skew = status.server_time_skew_ms
    skew_text = "?" if skew is None else f"{skew:+d} ms"
    balance_text = "?" if status.usdt_balance is None else f"{status.usdt_balance:,.2f}"
    equity_text = "?" if status.equity is None else f"{status.equity:,.2f}"

    lines = [
        f"Venue:            {status.venue.name:<25} Connection: ✔",
        f"Clock skew:       {skew_text:<25}",
        f"USDT balance:     {balance_text:<25} Equity (USDT): {equity_text}",
        "Holdings:",
    ]
    holdings = [
        h for h in (status.holdings or ()) if h.asset != "USDT" and not h.is_dust
    ]
    if not holdings:
        lines.append("  (none above dust threshold)")
    for holding in holdings:
        lines.append(
            f"  {holding.asset:<10} free {holding.free}  locked {holding.locked}"
        )
    return "\n".join(lines)
