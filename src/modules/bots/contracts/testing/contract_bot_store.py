"""The contract suite for `IBotStore` (HLD §10.3), run over the fake and the JSON store.

What the consumers rely on:

  · **the use cases** (`EPIC-029B`) rely on a round trip that loses nothing —
    the lifecycle's `run_started_at` and `recovering_from` among it, because
    trading derives inventory from the first (ADR D6) and `reconcile_ok` needs
    the second;
  · **create** relies on `exists()` seeing every taken id, including one whose
    file is unreadable, or a new bot could overwrite it;
  · **the Bots tab** relies on `load_all()` naming a refused file instead of
    dropping it, because the bot behind it may still own orders.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotNotFoundError,
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_CREATED = datetime(2026, 10, 3, 9, 30, tzinfo=UTC)
_STARTED = datetime(2026, 10, 3, 10, 0, 1, 250000, tzinfo=UTC)


def sample_bot(bot_id: str = "abc123", name: str = "grid one") -> StoredBot:
    """A bot with every field set to something a lossy store would drop."""
    return StoredBot(
        Bot(
            BotId(bot_id),
            BotDefinition(
                name=name,
                kind="grid",
                venue=TradingVenue.SPOT_TESTNET,
                symbol="BTCUSDT",
                config={"lower": "60000", "upper": "70000.5"},
            ),
            BotLifecycle(
                BotLifecycleState.RECOVERING,
                run_started_at=_STARTED,
                recovering_from=BotLifecycleState.PAUSED,
            ),
            _CREATED,
        ),
        runtime={"levels": [{"price": "61000", "state": "RESTING"}], "cycles": 3},
    )


class BotStoreContract:
    """Inherit this and provide `impl`."""

    @pytest.fixture
    def impl(self) -> IBotStore:
        raise NotImplementedError

    def test_a_round_trip_loses_nothing(self, impl: IBotStore) -> None:
        stored = sample_bot()
        impl.save(stored)
        assert impl.load(stored.bot.bot_id) == stored

    def test_saving_again_replaces_the_record(self, impl: IBotStore) -> None:
        impl.save(sample_bot(name="first"))
        impl.save(sample_bot(name="second"))
        assert impl.load(BotId("abc123")).bot.definition.name == "second"
        assert len(impl.load_all().bots) == 1

    def test_load_all_returns_every_bot(self, impl: IBotStore) -> None:
        impl.save(sample_bot("bbb222"))
        impl.save(sample_bot("aaa111"))
        ids = {stored.bot.bot_id.value for stored in impl.load_all().bots}
        assert ids == {"aaa111", "bbb222"}

    def test_an_empty_store_reads_empty(self, impl: IBotStore) -> None:
        reading = impl.load_all()
        assert reading.bots == ()
        assert reading.refused == ()

    def test_loading_an_unknown_bot_raises(self, impl: IBotStore) -> None:
        with pytest.raises(BotNotFoundError):
            impl.load(BotId("zzz999"))

    def test_delete_forgets_the_bot(self, impl: IBotStore) -> None:
        impl.save(sample_bot())
        impl.delete(BotId("abc123"))
        assert not impl.exists(BotId("abc123"))
        with pytest.raises(BotNotFoundError):
            impl.load(BotId("abc123"))

    def test_deleting_an_unknown_bot_raises(self, impl: IBotStore) -> None:
        with pytest.raises(BotNotFoundError):
            impl.delete(BotId("zzz999"))

    def test_exists_sees_a_saved_id(self, impl: IBotStore) -> None:
        assert not impl.exists(BotId("abc123"))
        impl.save(sample_bot())
        assert impl.exists(BotId("abc123"))
