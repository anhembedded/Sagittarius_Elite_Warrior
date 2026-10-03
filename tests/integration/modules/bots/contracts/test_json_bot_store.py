"""`EPIC-029B` — `JsonBotStore`: the contract on disk, atomic writes, refusals.

Integration rather than unit because the real store needs a directory;
`tmp_path` gives each test its own, so none touches `state/bots/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_restore_service import (
    BotRestoreService,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
    UnreadableBotError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.contract_bot_store import (
    BotStoreContract,
    sample_bot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FakeBotClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import BotLifecycle
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)


class TestJsonBotStore(BotStoreContract):
    @pytest.fixture
    def impl(self, tmp_path: Path) -> IBotStore:
        return JsonBotStore(tmp_path / "bots")


def test_the_file_is_named_by_the_bot_id_and_versioned(tmp_path: Path) -> None:
    store = JsonBotStore(tmp_path)
    store.save(sample_bot())
    record = json.loads((tmp_path / "abc123.json").read_text(encoding="utf-8"))
    assert record["schema_version"] == 1
    assert record["definition"]["bot_id"] == "abc123"
    assert record["lifecycle"]["state"] == "RECOVERING"
    assert record["runtime"]["cycles"] == 3


def test_a_crash_before_replace_leaves_the_previous_file_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = JsonBotStore(tmp_path)
    store.save(sample_bot(name="before"))
    before = (tmp_path / "abc123.json").read_bytes()

    def crash(self: Path, target: Path) -> Path:
        raise OSError("simulated crash between write and replace")

    monkeypatch.setattr(Path, "replace", crash)
    with pytest.raises(OSError, match="simulated crash"):
        store.save(sample_bot(name="after"))
    monkeypatch.undo()

    assert (tmp_path / "abc123.json").read_bytes() == before
    assert store.load(BotId("abc123")).bot.definition.name == "before"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["abc123.json"]


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ('{"schema_version": 2, "definition": {}}', "unknown schema_version 2"),
        ("{not json", "Expecting property name"),
        ('{"schema_version": 1, "definition": {}, "lifecycle": {}}', "bot_id"),
    ],
)
def test_an_unreadable_file_is_refused_by_name_never_dropped(
    tmp_path: Path, content: str, reason: str
) -> None:
    store = JsonBotStore(tmp_path)
    store.save(sample_bot("good11"))
    (tmp_path / "bad222.json").write_text(content, encoding="utf-8")

    reading = store.load_all()

    assert [s.bot.bot_id.value for s in reading.bots] == ["good11"]
    assert [r.name for r in reading.refused] == ["bad222.json"]
    assert reason in reading.refused[0].reason
    assert store.exists(BotId("bad222"))
    with pytest.raises(UnreadableBotError, match=reason):
        store.load(BotId("bad222"))


def test_a_file_whose_name_is_not_its_id_is_refused(tmp_path: Path) -> None:
    store = JsonBotStore(tmp_path)
    store.save(sample_bot("abc123"))
    (tmp_path / "abc123.json").rename(tmp_path / "zzz999.json")
    assert [r.name for r in store.load_all().refused] == ["zzz999.json"]


def test_a_missing_directory_reads_as_empty(tmp_path: Path) -> None:
    reading = JsonBotStore(tmp_path / "never_created").load_all()
    assert reading.bots == ()
    assert not (tmp_path / "never_created").exists()


@pytest.mark.parametrize(
    ("saved", "loaded"),
    [
        (BotLifecycleState.RUNNING, BotLifecycleState.RECOVERING),
        (BotLifecycleState.PAUSED, BotLifecycleState.RECOVERING),
        (BotLifecycleState.STARTING, BotLifecycleState.HALTED),
        (BotLifecycleState.STOPPING, BotLifecycleState.STOPPING),
        (BotLifecycleState.HALTED, BotLifecycleState.HALTED),
    ],
)
def test_a_restart_through_the_real_store_follows_d12(
    tmp_path: Path, saved: BotLifecycleState, loaded: BotLifecycleState
) -> None:
    store = JsonBotStore(tmp_path)
    original = sample_bot()
    bot = original.bot
    store.save(
        StoredBot(
            type(bot)(bot.bot_id, bot.definition, BotLifecycle(saved), bot.created_at),
            original.runtime,
        )
    )

    BotRestoreService(store, FakeBotClock()).restore_all()

    reloaded = JsonBotStore(tmp_path).load(BotId("abc123"))
    assert reloaded.bot.state is loaded
    assert reloaded.runtime == original.runtime
