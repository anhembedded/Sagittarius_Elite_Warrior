"""`EPIC-042B` — the attempt ledger is written inside `lifecycle` and a file without it still loads.

ADR 042 D4: the 24 h budget survives a restart because it is in the bot's file. The key is
additive, so `schema_version` stays 1 and a file written before the change reads as an empty
ledger. A file with a damaged ledger is refused by name, never read as "no attempts" (that
would hand a flapping bot a fresh budget).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import cast

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.bot_record_codec import (
    BotRecordError,
    decode,
    encode,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    JsonValue,
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    PRICE_FEED_STALE,
    USER_STREAM_DOWN,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.recovery_ledger import (
    RecoveryAttempt,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

T0 = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
ATTEMPTS = (
    RecoveryAttempt(PRICE_FEED_STALE, T0),
    RecoveryAttempt(USER_STREAM_DOWN, T0.replace(hour=13)),
)


def _stored(lifecycle: BotLifecycle) -> StoredBot:
    definition = BotDefinition("grid", "grid", TradingVenue.SPOT_TESTNET, "BTCUSDT")
    return StoredBot(Bot(BotId("abc123"), definition, lifecycle, T0), {})


def _record(stored: StoredBot) -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], json.loads(json.dumps(encode(stored))))


def test_the_ledger_and_the_waiting_state_round_trip_through_the_file() -> None:
    lifecycle = BotLifecycle(
        BotLifecycleState.AWAITING_RECOVERY, recovery_attempts=ATTEMPTS
    )
    loaded = decode(_record(_stored(lifecycle)))
    assert loaded.bot.lifecycle == lifecycle


def test_the_schema_version_does_not_move() -> None:
    assert (
        _record(_stored(BotLifecycle(BotLifecycleState.RUNNING)))["schema_version"] == 1
    )


def test_a_file_written_before_the_ledger_loads_with_none() -> None:
    record = _record(_stored(BotLifecycle(BotLifecycleState.HALTED)))
    lifecycle = cast(dict[str, JsonValue], record["lifecycle"])
    del lifecycle["recovery_attempts"]
    assert decode(record).bot.lifecycle.recovery_attempts == ()


@pytest.mark.parametrize(
    "damaged",
    ["not a list", [{"code": "price_feed_stale"}], [{"at": "x", "code": 1}], ["x"]],
)
def test_a_damaged_ledger_refuses_the_file_instead_of_resetting_the_budget(
    damaged: JsonValue,
) -> None:
    record = _record(_stored(BotLifecycle(BotLifecycleState.HALTED)))
    cast(dict[str, JsonValue], record["lifecycle"])["recovery_attempts"] = damaged
    with pytest.raises(BotRecordError):
        decode(record)
