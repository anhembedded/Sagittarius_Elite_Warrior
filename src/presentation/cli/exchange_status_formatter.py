"""Lays out `ExchangeConnectionStatus` as the two-shape report `EPIC-021D` §5
specifies — a success table, or a one-line failure plus guidance. Shared by
the headless (`exchange_status_cmd.py`) and interactive
(`ExchangeStatusCliHandler`) CLI entry points, so the two never drift.

`EPIC-038B` — this file no longer builds a string. It describes the rows
(`exchange_status_layout`) and `TextReportRenderer` turns them into the same
bytes as before (`tests/unit/presentation/cli/golden/`); `--json` renders the
payload (`exchange_status_payload.py`) of the same status from the same
`Report`, so the two views cannot disagree."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    Report,
    ReportCell,
    ReportRow,
    ReportSection,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AssetMode,
    FuturesAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.text_report_renderer import (
    TextReportRenderer,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

#: The label column of the aligned rows: a label is padded to this, then one
#: space, then the value column. Both are the widths the hand-built strings used.
_LABEL_WIDTH = 17
_VALUE_WIDTH = 25

#: python-binance's own default `recvWindow` — matches what
#: `FuturesSessionFactory.create_trading_client()` implicitly uses (no
#: override is passed), so this is the real threshold a request would be
#: judged against, not an arbitrary display cutoff.
RECV_WINDOW_MS = 5000

_FAILURE_GUIDANCE = EnumLabels(
    ConnectionFailureKind,
    {
        ConnectionFailureKind.NOT_CONFIGURED: (
            "API key/secret not configured. Get a key at testnet.binancefuture.com, "
            "then save it in Tools > Options > Trading or with the "
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
        ConnectionFailureKind.KEY_REJECTED: (
            "The exchange rejected the API key (Binance -2015). Likely causes: "
            "a key made for another environment (a mainnet key, say), an unknown "
            "key, an IP not on the key's allowlist (a LAN address such as "
            "192.168.x.x never matches; add the public one), or a key without "
            "the needed permission. Get a key at testnet.binancefuture.com, or "
            "use Add key… in Tools > Options > Trading to find which "
            "environment a key belongs to.\n"
            "  (Note: Spot Testnet keys and mainnet keys do NOT work here.)"
        ),
        ConnectionFailureKind.NETWORK: (
            "Could not connect to the exchange. Check your network/proxy and try again."
        ),
        ConnectionFailureKind.MAINTENANCE: (
            "The exchange is unavailable (maintenance or a gateway error). "
            "Try again later."
        ),
        ConnectionFailureKind.WITHDRAWAL_ENABLED: (
            "The API key can withdraw funds, so the app refuses it. Create a "
            "read-only key (reading only, withdrawals off) and use that."
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
        "then save it in Tools > Options > Trading or with the "
        "BINANCE_SPOT_TESTNET_API_KEY/BINANCE_SPOT_TESTNET_API_SECRET "
        "environment variables."
    ),
    ConnectionFailureKind.KEY_REJECTED: (
        "The exchange rejected the API key (Binance -2015). Likely causes: "
        "a key made for another environment (a mainnet key, say), an unknown "
        "key, an IP not on the key's allowlist (a LAN address such as "
        "192.168.x.x never matches; add the public one), or a key without "
        "the needed permission. Get a key at testnet.binance.vision, or use "
        "Add key… in Tools > Options > Trading to find which environment a "
        "key belongs to.\n"
        "  (Note: Futures Testnet keys and mainnet keys do NOT work here.)"
    ),
}


def _guidance_for(status: ExchangeConnectionStatus, kind: ConnectionFailureKind) -> str:
    if status.venue.market_type is MarketType.SPOT and kind in _SPOT_ONLY_GUIDANCE:
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


def _rows(*lines: str) -> tuple[ReportSection, ...]:
    return (ReportSection(None, tuple(ReportRow.of(line) for line in lines)),)


def _aligned(label: str, value: str, trailer: str | None = None) -> ReportRow:
    """`label`, `value` and an optional trailing cell in the fixed columns."""
    cells = [ReportCell(label, _LABEL_WIDTH), ReportCell(value, _VALUE_WIDTH)]
    if trailer is not None:
        cells.append(ReportCell(trailer))
    return ReportRow(tuple(cells))


def exchange_status_layout(
    status: ExchangeConnectionStatus,
) -> tuple[ReportSection, ...]:
    if status.failure is not None and not status.reachable:
        return _layout_unreachable(status)
    if status.failure is not None:
        return _layout_reachable_with_failure(status)
    return _layout_success(status)


def format_exchange_connection_status(status: ExchangeConnectionStatus) -> str:
    """The text report, for the interactive shell and the tests that pin it."""
    return TextReportRenderer().render(
        Report("exchange-status", 1, {}, exchange_status_layout(status))
    )


def _layout_unreachable(status: ExchangeConnectionStatus) -> tuple[ReportSection, ...]:
    kind = _require_failure_kind(status)
    return _rows(
        f"Venue: {status.venue.name}   Connection: ✘  {kind.name}",
        f"→ {_guidance_for(status, kind)}",
    )


def _layout_reachable_with_failure(
    status: ExchangeConnectionStatus,
) -> tuple[ReportSection, ...]:
    """Reachable, but a later check (Hedge Mode) blocks trade-readiness —
    show what was actually learned, then the guidance."""
    kind = _require_failure_kind(status)
    lines = [f"Venue: {status.venue.name}   Connection: ✔  but {kind.name}"]
    if status.usdt_balance is not None:
        lines.append(f"USDT balance: {status.usdt_balance:,.2f}")
    lines.append(f"→ {_guidance_for(status, kind)}")
    return _rows(*lines)


def _layout_success(status: ExchangeConnectionStatus) -> tuple[ReportSection, ...]:
    if status.venue.market_type is MarketType.SPOT:
        return _layout_spot_success(status)

    skew = status.server_time_skew_ms
    skew_text = "?" if skew is None else f"{skew:+d} ms"
    skew_safety = (
        ""
        if skew is None
        else (
            f"(recvWindow {RECV_WINDOW_MS} ms → safe)"
            if abs(skew) < RECV_WINDOW_MS
            else f"(recvWindow {RECV_WINDOW_MS} ms → WARNING, may hit -1021)"
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
    # column width, and one more row names the mode (PR #304 review,
    # finding 6).
    multi_assets = futures is not None and futures.asset_mode is AssetMode.MULTI_ASSETS
    available_label = "Available (USD):" if multi_assets else "Available (USDT):"
    asset_mode_rows = (
        [
            ReportRow(
                (
                    ReportCell("Asset mode:", _LABEL_WIDTH),
                    ReportCell("MULTI_ASSETS (every margin asset, in USD)"),
                )
            )
        ]
        if multi_assets
        else []
    )

    rows = (
        _aligned("Venue:", status.venue.name, "Connection: ✔"),
        _aligned("Clock skew:", skew_text, skew_safety),
        _aligned(
            "Position mode:", position_mode_text, f"Margin type: {margin_type_text}"
        ),
        _aligned(
            "Wallet (USDT):", balance_text, f"Open positions: {open_positions_text}"
        ),
        _aligned(available_label, available_text, f"Unrealized PnL: {upnl_text}"),
        *asset_mode_rows,
    )
    return (ReportSection(None, rows),)


def _layout_spot_success(status: ExchangeConnectionStatus) -> tuple[ReportSection, ...]:
    """`EPIC-027H` — Spot has no position mode/margin type to show, and a
    list of per-asset holdings instead of one USDT wallet figure. `?` for
    `equity` means "not available" (`SpotAccountReader` never guesses a
    partial sum), never a silently-omitted line."""
    skew = status.server_time_skew_ms
    skew_text = "?" if skew is None else f"{skew:+d} ms"
    balance_text = "?" if status.usdt_balance is None else f"{status.usdt_balance:,.2f}"
    equity_text = "?" if status.equity is None else f"{status.equity:,.2f}"

    rows = [
        _aligned("Venue:", status.venue.name, "Connection: ✔"),
        _aligned("Clock skew:", skew_text),
        _aligned("USDT balance:", balance_text, f"Equity (USDT): {equity_text}"),
        ReportRow.of("Holdings:"),
    ]
    holdings = [
        h for h in (status.holdings or ()) if h.asset != "USDT" and not h.is_dust
    ]
    if not holdings:
        rows.append(ReportRow.of("  (none above dust threshold)"))
    for holding in holdings:
        rows.append(
            ReportRow.of(
                f"  {holding.asset:<10} free {holding.free}  locked {holding.locked}"
            )
        )
    return (ReportSection(None, tuple(rows)),)
