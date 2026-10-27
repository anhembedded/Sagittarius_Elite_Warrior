"""`EPIC-047C` - the host-facts file as the bridge shows it: the last good document, and whether the host lives."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_host_facts_view import (
    FileHostFactsView,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.json_host_facts_codec import (
    JsonHostFactsCodec,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_facts_watch import (
    LIVE_AFTER_HEARTBEATS,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsDocument,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.bridge_values import (
    FactsState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.host_facts.host_facts_world import (
    SteppingClock,
    document,
)

ROOT = "sew.host-facts-document/1"
codec = JsonHostFactsCodec()


class World:
    def __init__(self, tmp_path: Path) -> None:
        self.path = tmp_path / "host-facts.json"
        self.clock = SteppingClock()
        self.view = FileHostFactsView(self.path, codec, self.clock, ROOT)

    def host_writes(self, written: HostFactsDocument) -> None:
        self.path.write_bytes(codec.encode(written))


def test_there_is_no_file_before_the_host_has_written_one(tmp_path: Path) -> None:
    world = World(tmp_path)

    look = world.view.look()

    assert look.state is FactsState.MISSING
    assert (look.document, look.age_s, look.revision) == (None, None, 0)
    assert "no file" in look.problem


def test_a_file_the_host_wrote_is_live_and_carries_its_document(tmp_path: Path) -> None:
    world = World(tmp_path)
    written = document(5)
    world.host_writes(written)

    look = world.view.look()

    assert look.state is FactsState.LIVE
    assert look.revision == 5
    assert look.document is not None
    assert (look.document.root, look.document.value) == (ROOT, written)
    assert look.age_s == 0
    assert look.problem == ""


def test_a_host_quiet_for_more_than_three_heartbeats_is_stale_not_gone(
    tmp_path: Path,
) -> None:
    world = World(tmp_path)
    world.host_writes(document(5, heartbeat_s=15))

    world.clock.advance(LIVE_AFTER_HEARTBEATS * 15)
    on_the_edge = world.view.look()
    world.clock.advance(1)
    past_it = world.view.look()

    assert on_the_edge.state is FactsState.LIVE
    assert past_it.state is FactsState.STALE
    assert past_it.document is not None  # the facts are kept, and said to be old


def test_a_torn_file_keeps_the_last_good_document_and_says_why(tmp_path: Path) -> None:
    world = World(tmp_path)
    world.host_writes(document(5))
    world.view.look()

    world.path.write_bytes(b'{"schema": "sew.host-facts/1", "revi')
    look = world.view.look()

    assert (look.revision, look.state) == (5, FactsState.LIVE)
    assert look.document is not None
    assert "unreadable" in look.problem and "last good one is kept" in look.problem


def test_a_deleted_file_keeps_the_last_good_document(tmp_path: Path) -> None:
    world = World(tmp_path)
    world.host_writes(document(5))
    world.view.look()

    world.path.unlink()
    look = world.view.look()

    assert look.revision == 5
    assert "no file" in look.problem and "last good one is kept" in look.problem


def test_an_older_revision_never_replaces_a_newer_one(tmp_path: Path) -> None:
    world = World(tmp_path)
    world.host_writes(document(9))
    world.view.look()

    world.host_writes(document(8))
    look = world.view.look()

    assert look.revision == 9
    assert "older revision" in look.problem


def test_a_newer_revision_replaces_the_document_and_clears_the_problem(
    tmp_path: Path,
) -> None:
    world = World(tmp_path)
    world.host_writes(document(5))
    world.view.look()
    world.path.write_bytes(b"torn")
    world.view.look()

    newer = document(6)
    world.host_writes(newer)
    look = world.view.look()

    assert (look.revision, look.problem) == (6, "")
    assert look.document is not None and look.document.value == newer


def test_a_file_of_another_schema_is_never_taken_for_the_hosts(tmp_path: Path) -> None:
    world = World(tmp_path)
    world.path.write_text('{"schema": "sew.health/1"}', encoding="utf-8")

    look = world.view.look()

    assert look.state is FactsState.MISSING
    assert "unreadable" in look.problem


@pytest.mark.parametrize("heartbeat", [1, 15, 60])
def test_the_hosts_own_heartbeat_sets_how_long_quiet_is_allowed(
    tmp_path: Path, heartbeat: int
) -> None:
    world = World(tmp_path)
    written = document(5)
    world.host_writes(
        replace(written, header=replace(written.header, heartbeat_s=heartbeat))
    )

    world.clock.advance(LIVE_AFTER_HEARTBEATS * heartbeat + 1)

    assert world.view.look().state is FactsState.STALE
