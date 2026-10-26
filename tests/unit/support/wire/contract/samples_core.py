"""`EPIC-047A` — a full and a minimal instance of the host-control request and reply (`core/contracts`).

See `samples_trading.py` for what *full* and *minimal* mean.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    ADD_SUBJECT,
    HostControlAction,
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)


def full_request() -> HostControlRequest:
    return HostControlRequest(
        HostControlAction.APPLY_ENTRY,
        "plan",
        confirmed_venue="futures_mainnet",
        close_position=True,
        settings=(
            ParameterSetting("lower", "60000.00"),
            ParameterSetting("upper", "70000"),
        ),
        entry=NewBotEntry(
            "BTC grid",
            "grid",
            "futures_testnet",
            "BTCUSDT",
            (ParameterSetting("levels", "10"),),
        ),
        to_venue="spot_testnet",
        proposal="p-7",
        strategy_venue="spot_testnet",
        desired_state="running",
    )


def minimal_request() -> HostControlRequest:
    return HostControlRequest(HostControlAction.STOP, "b-0001")


def add_request() -> HostControlRequest:
    return HostControlRequest(
        HostControlAction.ADD,
        ADD_SUBJECT,
        entry=NewBotEntry("ETH grid", "grid", "spot_testnet", "ETHUSDT"),
    )


def full_reply() -> HostControlReply:
    return HostControlReply(
        HostControlStatus.REFUSED, "BTCUSDT is leased by b-0009", "c-123", "b-0001"
    )


def minimal_reply() -> HostControlReply:
    return HostControlReply(HostControlStatus.DONE, "stopped")
