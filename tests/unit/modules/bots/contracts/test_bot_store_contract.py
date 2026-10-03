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
