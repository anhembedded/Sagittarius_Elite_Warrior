"""`EPIC-047C` - the bots' files as the bridge reads them: a stamp per write, a bot per file, nothing written."""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.store_bridge_bots import (
    BOT_LIST_ROOT,
    BOT_SNAPSHOT_ROOT,
    StoreBridgeBots,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots.result import (
    BotList,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import seed


def _world(tmp_path: Path) -> tuple[JsonBotStore, StoreBridgeBots]:
    directory = tmp_path / "bots"
    return JsonBotStore(directory), StoreBridgeBots(directory)


def _save(store: JsonBotStore, bot_id: str, state: BotLifecycleState) -> None:
    seed(store, bot_id, state)  # type: ignore[arg-type]


def test_a_directory_that_does_not_exist_holds_no_bots(tmp_path: Path) -> None:
    bridge = StoreBridgeBots(tmp_path / "nowhere")

    assert dict(bridge.stamps()) == {}
    assert bridge.listing().value == BotList()


def test_every_bot_file_has_a_stamp_and_a_write_changes_it(tmp_path: Path) -> None:
    store, bridge = _world(tmp_path)
    _save(store, "aaaaaa", BotLifecycleState.DRAFT)
    _save(store, "bbbbbb", BotLifecycleState.DRAFT)
    before = dict(bridge.stamps())

    _save(store, "aaaaaa", BotLifecycleState.STOPPED)
    after = dict(bridge.stamps())

    assert set(before) == {"aaaaaa", "bbbbbb"}
    assert after["aaaaaa"] != before["aaaaaa"]
    assert after["bbbbbb"] == before["bbbbbb"]


def test_a_deleted_bot_has_no_stamp(tmp_path: Path) -> None:
    store, bridge = _world(tmp_path)
    _save(store, "aaaaaa", BotLifecycleState.DRAFT)

    (tmp_path / "bots" / "aaaaaa.json").unlink()

    assert dict(bridge.stamps()) == {}


@pytest.mark.parametrize(
    "name", ["notes.txt", "aaaaaa.json.tmp", "UPPER.json", ".json", "a b.json"]
)
def test_a_file_that_is_not_a_bots_is_not_listed(tmp_path: Path, name: str) -> None:
    _, bridge = _world(tmp_path)
    (tmp_path / "bots").mkdir()
    (tmp_path / "bots" / name).write_text("{}", encoding="utf-8")

    assert dict(bridge.stamps()) == {}


def test_a_bots_file_is_read_as_the_snapshot_the_bots_tab_shows(tmp_path: Path) -> None:
    store, bridge = _world(tmp_path)
    _save(store, "aaaaaa", BotLifecycleState.STOPPED)

    reading = bridge.read("aaaaaa")

    assert reading.bot is not None
    assert reading.bot.root == BOT_SNAPSHOT_ROOT
    assert isinstance(reading.bot.value, BotSnapshot)
    assert reading.bot.value.bot_id == "aaaaaa"
    assert reading.bot.value.state is BotLifecycleState.STOPPED
    assert reading.refused == ""


def test_a_file_that_is_gone_reads_as_nothing_not_as_an_error(tmp_path: Path) -> None:
    _, bridge = _world(tmp_path)

    reading = bridge.read("aaaaaa")

    assert (reading.bot, reading.refused) == (None, "")


def test_a_file_that_cannot_be_decoded_is_refused_in_words(tmp_path: Path) -> None:
    _, bridge = _world(tmp_path)
    (tmp_path / "bots").mkdir()
    (tmp_path / "bots" / "aaaaaa.json").write_text(
        '{"schema_version": 9}', encoding="utf-8"
    )

    reading = bridge.read("aaaaaa")

    assert reading.bot is None
    assert "schema_version" in reading.refused


def test_the_listing_is_the_bots_own_oldest_first_with_the_refused_files(
    tmp_path: Path,
) -> None:
    store, bridge = _world(tmp_path)
    _save(store, "aaaaaa", BotLifecycleState.DRAFT)
    (tmp_path / "bots" / "zzzzzz.json").write_text("not json", encoding="utf-8")

    listing = bridge.listing()

    assert listing.root == BOT_LIST_ROOT
    assert isinstance(listing.value, BotList)
    assert [b.bot_id for b in listing.value.bots] == ["aaaaaa"]
    assert [r.name for r in listing.value.refused] == ["zzzzzz.json"]


def test_the_bridge_writes_nothing_however_it_is_used(tmp_path: Path) -> None:
    store, bridge = _world(tmp_path)
    _save(store, "aaaaaa", BotLifecycleState.DRAFT)
    before = sorted(
        (p.name, p.stat().st_mtime_ns) for p in (tmp_path / "bots").iterdir()
    )

    bridge.stamps()
    bridge.read("aaaaaa")
    bridge.listing()

    assert before == sorted(
        (p.name, p.stat().st_mtime_ns) for p in (tmp_path / "bots").iterdir()
    )
