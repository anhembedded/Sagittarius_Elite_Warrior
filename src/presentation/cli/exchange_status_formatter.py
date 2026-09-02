"""Renders `ExchangeConnectionStatus` as the two-shape text `EPIC-021D` §5
specifies — a success table, or a one-line failure plus guidance. Shared by
the headless (`exchange_status_cmd.py`) and interactive
(`ExchangeStatusCliHandler`) CLI entry points, so the two never drift."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)

#: python-binance's own default `recvWindow` — matches what
#: `ExchangeSessionFactory.create_trading_client()` implicitly uses (no
#: override is passed), so this is the real threshold a request would be
#: judged against, not an arbitrary display cutoff.
_RECV_WINDOW_MS = 5000

_FAILURE_GUIDANCE: dict[ConnectionFailureKind, str] = {
    ConnectionFailureKind.NOT_CONFIGURED: (
        "Chưa cấu hình API key/secret. Lấy key tại testnet.binancefuture.com, "
        "rồi lưu qua màn Settings hoặc biến môi trường "
        "BINANCE_FUTURES_TESTNET_API_KEY/BINANCE_FUTURES_TESTNET_API_SECRET."
    ),
    ConnectionFailureKind.BAD_SIGNATURE: (
        "Chữ ký request không hợp lệ. Kiểm tra lại API Secret đã sao chép "
        "đúng, không thừa hay thiếu ký tự."
    ),
    ConnectionFailureKind.CLOCK_SKEW: (
        "Đồng hồ máy lệch quá xa giờ sàn. Đồng bộ lại giờ hệ thống (NTP) rồi thử lại."
    ),
    ConnectionFailureKind.KEY_EXPIRED: (
        "Key testnet đã hết hạn hoặc bị reset. Lấy key mới tại "
        "testnet.binancefuture.com.\n"
        "  (Lưu ý: key Spot Testnet và key mainnet KHÔNG dùng được ở đây.)"
    ),
    ConnectionFailureKind.NETWORK: (
        "Không kết nối được tới sàn. Kiểm tra mạng/proxy rồi thử lại."
    ),
    ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED: (
        "Tài khoản đang ở Hedge Mode. Epic này giả định One-way Mode — đổi "
        "lại ở Binance Futures > Settings > Position Mode trên web/app "
        "Binance, rồi kiểm tra kết nối lại."
    ),
}


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
    lines = [f"Venue: {status.venue.name}   Kết nối: ✘  {kind.name}"]
    lines.append(f"→ {_FAILURE_GUIDANCE[kind]}")
    return "\n".join(lines)


def _format_reachable_with_failure(status: ExchangeConnectionStatus) -> str:
    """Reachable, but a later check (Hedge Mode) blocks trade-readiness —
    show what was actually learned, then the guidance."""
    kind = _require_failure_kind(status)
    lines = [f"Venue: {status.venue.name}   Kết nối: ✔  nhưng {kind.name}"]
    if status.usdt_balance is not None:
        lines.append(f"Số dư USDT: {status.usdt_balance:,.2f}")
    lines.append(f"→ {_FAILURE_GUIDANCE[kind]}")
    return "\n".join(lines)


def _format_success(status: ExchangeConnectionStatus) -> str:
    skew = status.server_time_skew_ms
    skew_text = "?" if skew is None else f"{skew:+d} ms"
    skew_safety = (
        ""
        if skew is None
        else (
            f"(recvWindow {_RECV_WINDOW_MS} ms → an toàn)"
            if abs(skew) < _RECV_WINDOW_MS
            else f"(recvWindow {_RECV_WINDOW_MS} ms → CẢNH BÁO, có thể bị -1021)"
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
            f"Venue:            {status.venue.name:<25} Kết nối: ✔",
            f"Lệch đồng hồ:     {skew_text:<25} {skew_safety}",
            f"Position mode:    {position_mode_text:<25} Margin type: {margin_type_text}",
            f"Số dư USDT:       {balance_text:<25} Vị thế đang mở: {open_positions_text}",
        ]
    )
