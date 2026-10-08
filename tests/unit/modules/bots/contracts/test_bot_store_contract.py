"""`EPIC-029B` — the fake store passes the store's contract suite (HLD §10.3).

The same suite runs against `JsonBotStore` in the integration tier, where it
has a directory to write to.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    UnreadableBotError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.contract_bot_store import (
    BotStoreContract,
    sample_bot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId


class TestFakeBotStore(BotStoreContract):
    @pytest.fixture
    def impl(self) -> IBotStore:
        return FakeBotStore()


def test_refuse_file_makes_the_id_taken_unreadable_and_listed() -> None:
    """The fake's own helper, verified (`test_fake_helpers_are_verified.py`)."""
    store = FakeBotStore()
    store.save(sample_bot())
    store.refuse_file(BotId("abc123"), "unknown schema_version 2")

    assert store.exists(BotId("abc123"))
    with pytest.raises(UnreadableBotError, match="unknown schema_version 2"):
        store.load(BotId("abc123"))
    reading = store.load_all()
    assert reading.bots == ()
    assert [(r.name, r.reason) for r in reading.refused] == [
        ("abc123.json", "unknown schema_version 2")
    ]


def test_fail_saves_raises_until_healed_and_keeps_the_last_good_record() -> None:
    """The fake's own helper, verified (`test_fake_helpers_are_verified.py`)."""
    store = FakeBotStore()
    stored = sample_bot()
    store.save(stored)
    store.fail_saves(OSError("disk full"))

    with pytest.raises(OSError, match="disk full"):
        store.save(stored)
    assert store.load(stored.bot.bot_id) == stored

    store.heal()
    store.save(stored)


def test_fail_saves_for_a_count_heals_itself_and_counts_the_refusals() -> None:
    """`times` is the fake's own helper too: a store that fails N writes, then recovers."""
    store = FakeBotStore()
    stored = sample_bot()
    store.fail_saves(OSError("disk full"), times=2)

    for _ in range(2):
        with pytest.raises(OSError, match="disk full"):
            store.save(stored)
    store.save(stored)

    assert store.failed_saves == 2
    assert store.load(stored.bot.bot_id) == stored
