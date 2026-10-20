"""`EPIC-026L` — what the owner reads about the cap: the health section and the pre-flight."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckCause,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import IConfigReader
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.loss_cap.loss_cap_health_contributor import (
    SECTION_NAME,
    LossCapHealthContributor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.loss_cap.loss_cap_preflight_check import (
    LossCapPreflightCheck,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_store import (
    ILossCapStore,
    LossCapRecordUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_ledger import (
    LossCapLedger,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_policy import (
    LossCapRecord,
    LossCapTrip,
    LossCapTripReason,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import seed
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
)

from .loss_cap_world import MORNING, BotsWorld, MemoryLossCapStore, bot, build


class _Config(IConfigReader):
    def __init__(self, figure: object) -> None:
        self.figure = figure

    def get(self, key: str, default: Any = None) -> Any:
        assert key == "bots.account_loss_cap"
        return default if self.figure is None else self.figure


class _UnreadableStore(ILossCapStore):
    def read(self) -> LossCapRecord | None:
        raise LossCapRecordUnreadableError(
            "the loss-cap record loss_cap.json cannot be read"
        )

    def write(self, record: LossCapRecord) -> None:
        raise AssertionError("a check writes nothing")


def _check(
    figure: object, *, record: ILossCapStore | None = None, on: str | None = None
) -> LossCapPreflightCheck:
    bots = FakeBotStore()
    if on is not None:
        stored = seed(bots, BOT, BotLifecycleState.DRAFT, config=CONFIG, runtime={})
        moved = replace(
            stored, definition=replace(stored.definition, venue=TradingVenue(on))
        )
        bots.save(StoredBot(moved, {}))
    return LossCapPreflightCheck(_Config(figure), record or MemoryLossCapStore(), bots)


def test_the_health_section_says_the_figure_and_that_it_is_not_tripped_and_no_money() -> (
    None
):
    world = build(BotsWorld(bot("aaa111", "-120")))
    world.sample()

    section = LossCapHealthContributor(world.cap).snapshot()

    assert LossCapHealthContributor(world.cap).name == SECTION_NAME
    assert section["figure"] == "500 USDT" and section["tripped"] is False
    assert "day_pnl" not in section  # the snapshot file carries no profit or loss
    assert world.cap.status().day_pnl == Decimal(-120)


def test_the_health_section_says_so_when_the_cap_is_off() -> None:
    world = build(BotsWorld(), figure=None)

    section = LossCapHealthContributor(world.cap).snapshot()

    assert section["figure"] is None and section["tripped"] is False


def test_a_figure_that_is_set_and_cannot_be_read_fails_the_check_as_the_owners_to_fix() -> (
    None
):
    result = _check("five hundred").run(PreflightScope())

    assert (
        result.status is CheckStatus.FAIL and result.cause is CheckCause.CONFIGURATION
    )


def test_a_set_figure_passes_and_is_named() -> None:
    result = _check("500 USDT").run(PreflightScope())

    assert result.status is CheckStatus.PASS
    assert "500 USDT" in result.findings[0].reason


def test_no_figure_on_a_mainnet_venue_is_a_warning_that_says_nothing_stops_the_loss() -> (
    None
):
    result = _check(None).run(PreflightScope(venue="spot_mainnet"))

    assert result.status is CheckStatus.WARN
    assert "off" in result.findings[0].reason and "mainnet" in result.findings[0].reason


def test_no_figure_when_a_stored_bot_is_on_mainnet_is_the_same_warning() -> None:
    assert (
        _check(None, on="futures_mainnet").run(PreflightScope()).status
        is CheckStatus.WARN
    )


@pytest.mark.parametrize("venue", ["spot_testnet", "futures_testnet"])
def test_no_figure_on_testnet_is_a_pass_that_says_the_cap_is_off(venue: str) -> None:
    result = _check(None).run(PreflightScope(venue=venue))

    assert result.status is CheckStatus.PASS and "off" in result.findings[0].reason


def test_a_tripped_record_warns_that_no_bot_will_start_until_acknowledged() -> None:
    clock = MORNING
    trip = LossCapTrip(
        LossCapTripReason.LOSS_REACHED,
        clock,
        clock.date(),
        None,
        "500 USDT",
        "the loss reached the cap",
    )
    record = MemoryLossCapStore(LossCapRecord(LossCapLedger.empty(clock.date()), trip))

    result = _check("500 USDT", record=record).run(PreflightScope())

    assert result.status is CheckStatus.WARN
    assert any("acknowledged" in f.reason for f in result.findings)
    assert any("loss-cap-ack" in f.remedy for f in result.findings)


def test_a_record_that_cannot_be_read_warns_that_the_cap_starts_tripped() -> None:
    result = _check("500 USDT", record=_UnreadableStore()).run(PreflightScope())

    assert result.status is CheckStatus.WARN
    assert any("starts tripped" in f.reason for f in result.findings)


def test_a_tripped_health_section_names_the_reason_and_never_the_amount() -> None:
    world = build(BotsWorld(bot("aaa111", "-612.34")))
    world.sample()

    section = LossCapHealthContributor(world.cap).snapshot()

    assert section["tripped"] is True and section["trip_reason"] == "loss_reached"
    assert "612" not in str(section) and "trip_detail" not in section
