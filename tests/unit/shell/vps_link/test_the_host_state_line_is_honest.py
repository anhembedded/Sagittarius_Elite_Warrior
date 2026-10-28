"""`EPIC-047E` (O5, D5) - the line above the VPS tab says which host, what it holds, whether it is connected and how old the data is."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_world import HostWorld
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

HEARD = datetime(2026, 10, 27, 12, 0, 5, tzinfo=UTC)
WORLD = HostWorld(held=full_host_facts().facts, heard_at=HEARD, connected=True)


def test_a_connected_tab_names_the_host_the_key_and_the_age_of_its_data() -> None:
    line = host_state_line(
        "nathan-warrior",
        WORLD,
        LinkStatus(LinkState.CONNECTED, "connected"),
        HEARD + timedelta(seconds=2),
    )

    assert line.connected
    assert line.text == (
        "nathan-warrior · Spot Testnet key saved · connected · updated 2 s ago"
    )


def test_a_disconnected_tab_says_so_with_the_time_the_data_is_from() -> None:
    status = LinkStatus(
        LinkState.RECONNECTING,
        f"{disconnected_words(HEARD)}; reconnecting (attempt 2)",
        HEARD,
        2,
    )

    line = host_state_line(
        "nathan-warrior", WORLD, status, HEARD + timedelta(minutes=5)
    )

    assert not line.connected
    assert "disconnected, data as of 12:00:05 UTC" in line.text
    assert "connected ·" not in line.text
    assert "updated" not in line.text


def test_a_host_that_published_nothing_is_not_described_by_a_default() -> None:
    line = host_state_line(
        "nathan-warrior",
        replace(WORLD, held=None, heard_at=None),
        LinkStatus(LinkState.CONNECTED, "connected"),
        HEARD,
    )

    assert "the host has published no facts yet" in line.text
    assert "no data yet" in line.text
