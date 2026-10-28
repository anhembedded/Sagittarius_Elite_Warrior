"""`EPIC-047E` (O5, D5) - the line above the VPS tab says which host, what it holds, whether it is connected and how current its facts are."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_world import (
    HostFile,
    HostFileState,
    HostWorld,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.host_state_line import (
    host_state_line,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_status import (
    LinkState,
    LinkStatus,
    disconnected_words,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_operations import (
    full_host_facts,
)

LOOKED = datetime(2026, 10, 27, 12, 0, 5, tzinfo=UTC)
CONNECTED = LinkStatus(LinkState.CONNECTED, "connected")
LIVE_WORLD = HostWorld(
    held=full_host_facts().facts,
    held_file=HostFile(HostFileState.LIVE, 0.0, LOOKED),
    last_frame_at=LOOKED,
    connected=True,
)


def test_a_connected_tab_names_the_host_the_key_and_how_old_the_facts_are() -> None:
    line = host_state_line(
        "nathan-warrior", LIVE_WORLD, CONNECTED, LOOKED + timedelta(seconds=2)
    )

    assert line.ok
    assert line.text == (
        "nathan-warrior · Spot Testnet key saved · connected · facts updated 2 s ago"
    )


def test_a_quiet_host_is_not_called_updated_whatever_else_the_link_heard() -> None:
    """The bridge keeps the last document of a host that stopped writing; a heartbeat or a bot event that
    arrives meanwhile proves the link, not the facts."""
    now = LOOKED + timedelta(seconds=62)
    quiet = replace(
        LIVE_WORLD,
        held_file=HostFile(HostFileState.STALE, 60.0, LOOKED),
        last_frame_at=now,
    )

    line = host_state_line("nathan-warrior", quiet, CONNECTED, now)

    assert "host quiet: facts last written 122 s ago, it may have stopped" in line.text
    assert "updated" not in line.text


def test_a_disconnected_tab_says_so_with_the_time_the_data_is_from() -> None:
    status = LinkStatus(
        LinkState.RECONNECTING,
        f"{disconnected_words(LOOKED)}; reconnecting (attempt 2)",
        LOOKED,
        2,
    )

    line = host_state_line(
        "nathan-warrior", LIVE_WORLD, status, LOOKED + timedelta(minutes=5)
    )

    assert not line.ok
    assert "disconnected, data as of 12:00:05 UTC" in line.text
    assert "connected ·" not in line.text
    assert "updated" not in line.text


def test_a_host_that_published_nothing_is_not_described_by_a_default() -> None:
    line = host_state_line(
        "nathan-warrior",
        replace(LIVE_WORLD, held=None, held_file=HostFile()),
        CONNECTED,
        LOOKED,
    )

    assert line.text.count("the host has published no facts yet") == 2
