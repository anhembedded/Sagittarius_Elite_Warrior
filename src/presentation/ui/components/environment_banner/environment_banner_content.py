"""What the environment banner says, computed once from `VenueAlignment`
(`EPIC-021K`).

@details `EXCHANGE_MARKET_DATA_VENUE`/`EXCHANGE_TRADING_VENUE` are read
only at boot (`resolve_market_data_venue`/`resolve_trading_venue`,
`binance_endpoints.py`) — Settings has no UI control for either (grep
confirms), so both are file-edit-and-restart config, same tier as
`DEFAULT_SYMBOLS`/`DEFAULT_INTERVAL`. `VenueAlignment` is therefore fixed
for the whole session, and `EnvironmentBannerContent` needs no signal to
notify a change that can never happen — it is a plain, immutable
projection, not a reactive ViewModel.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.value_objects.venue_alignment import (
    VenueAlignment,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit.style import StyleRole
from Sagittarius_Elite_Warrior.src.presentation.ui.kit.surfaces.banner import Severity

#: Vietnamese copy, verbatim from the task's own worked mock (`EPIC-021K`
#: §2.1's table) — not re-worded here, since it is the exact text the
#: mockup was reviewed and approved against.
_CONTENT: dict[VenueAlignment, tuple[str, str, StyleRole]] = {
    VenueAlignment.TRADING_DISABLED: (
        "⏸",
        "Giao dịch đang TẮT. Chỉ xem dữ liệu.",
        Severity.INFO,
    ),
    VenueAlignment.ALIGNED: (
        "ⓘ",
        "FUTURES TESTNET — tiền giả lập.",
        Severity.WARN,
    ),
    VenueAlignment.DATA_MAINNET_ORDERS_TESTNET: (
        "⚠",
        "Chart đang hiển thị giá MAINNET, lệnh khớp trên TESTNET. Giá thấy ≠ giá khớp.",
        Severity.DANGER,
    ),
}


@dataclass(frozen=True)
class EnvironmentBannerContent:
    """@brief Everything `EnvironmentBanner` renders — icon, message,
    severity — as plain, already-decided values. No `VenueAlignment`
    logic lives in the widget itself."""

    icon: str
    message: str
    severity: StyleRole


def venue_alignment_banner_content(
    alignment: VenueAlignment,
) -> EnvironmentBannerContent:
    icon, message, severity = _CONTENT[alignment]
    return EnvironmentBannerContent(icon=icon, message=message, severity=severity)
