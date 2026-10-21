"""`EPIC-044C` - the heartbeat counts a bot waiting for its range apart and says what it waits on.

The counts line already groups bots by the state the report spells; what a waiting bot needs
added is its range and the price it waits on, in the Plan's words (`waiting_text`).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.application.heartbeat_text import (
    heartbeat_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusReport,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import (
    grid_ladder_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.heartbeat_world import (
    beats_of,
    service_of,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.sources.bot_source_world import (
    Bots,
    entry,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import build_rig

_NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
_CONFIG = {
    "lower": "100",
    "upper": "140",
    "grid_count": "4",
    "spacing": "ARITHMETIC",
    "capital_quote": "1000",
    "stop_loss": "off",
    "take_profit": "off",
}


def _waiting_entry(price: str | None = "95"):
    progress = BotProgress(
        realised_profit=Decimal(0),
        completed_cycles=0,
        open_orders=0,
        inventory=Decimal(0),
        average_cost=None,
        reason="",
        reason_detail="",
        mark_price=None if price is None else Decimal(price),
    )
    snapshot = BotSnapshot(
        bot_id="w1",
        name="waiting-grid",
        kind="grid",
        venue=TradingVenue.SPOT_MAINNET,
        symbol="ETHUSDT",
        state=BotLifecycleState.AWAITING_RANGE,
        created_at=_NOW,
        run_started_at=_NOW,
        config=_CONFIG,
        progress=progress,
    )
    return replace(
        entry(BotLifecycleState.AWAITING_RANGE.value),
        bot_id="w1",
        name="waiting-grid",
        ladder=grid_ladder_of(snapshot, _NOW),
    )


def test_a_waiting_bot_is_counted_apart_and_listed_with_its_range_and_price() -> None:
    running = replace(entry("RUNNING"), bot_id="r1", name="btc-grid")

    text = heartbeat_text(BotStatusReport(bots=(running, _waiting_entry())))

    assert "1 AWAITING_RANGE, 1 RUNNING" in text
    line = next(row for row in text.splitlines() if row.startswith("- waiting-grid"))
    assert "Waiting for the price to enter 100.0000–140.0000 (now 95.0000)" in line


def test_a_waiting_bot_that_heard_no_price_does_not_invent_one() -> None:
    text = heartbeat_text(BotStatusReport(bots=(_waiting_entry(None),)))

    assert "(no price heard yet)" in text


def test_a_bot_with_a_reason_keeps_it_over_the_wait_sentence() -> None:
    mixed = replace(_waiting_entry(), reason="user_stream_down")

    text = heartbeat_text(BotStatusReport(bots=(mixed,)))

    assert "AWAITING_RANGE - user_stream_down" in text
    assert "Waiting for the price" not in text


def test_the_service_sends_the_waiting_bots_line_in_the_heartbeat(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)

    service_of(rig, Bots(_waiting_entry())).tick()

    [text] = beats_of(rig)
    assert "waiting-grid" in text and "(now 95.0000)" in text
