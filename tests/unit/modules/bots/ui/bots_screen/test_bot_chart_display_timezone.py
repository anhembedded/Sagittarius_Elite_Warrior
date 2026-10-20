"""`BOT-205` — the selected bot's chart reads in the display time zone the owner chose.

The machine is injected through `machine_local_time`, the one place the service asks the OS,
so no test depends on the runner's `TZ`: an owner on UTC+7 who picks "System" must read local
time on the chart's axis and its crosshair label, not UTC."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bot_tick_feed import BotTickFeed
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_chart_host import (
    BotChartHost,
    BotChartPorts,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.ui_kit.display_timezone_combo import (
    DisplayTimezoneCombo,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services import (
    display_timezone_service as service,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.chart.bot_chart_fixtures import (
    ChartWorld,
    InlineThreadManager,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)

from .bots_screen_fixtures import stored

_CANDLE_TIME = datetime(2026, 10, 19, 12, 1, 30, tzinfo=UTC).timestamp()


def _machine_in_utc_plus_7(moment: datetime) -> datetime:
    """What the OS answers on the owner's machine: a fixed offset named `+07`, not an IANA key."""
    return moment.astimezone(timezone(timedelta(hours=7), "+07"))


@dataclass
class _Open:
    host: BotChartHost
    card: ChartCard
    preference: DisplayTimezonePreference
    readouts: list[str]

    def crosshair_time(self) -> str:
        self.card.crosshair._update_label(_CANDLE_TIME, 1.0)
        return self.readouts[-1]

    def axis_zone(self) -> str:
        return self.card.plot_layout.main_plot.getAxis("bottom").display_zone


@pytest.fixture
def opened(qapp, monkeypatch: pytest.MonkeyPatch) -> _Open:
    monkeypatch.setattr(service, "machine_local_time", _machine_in_utc_plus_7)
    preference = DisplayTimezonePreference()
    world = ChartWorld()
    host = BotChartHost(
        BotChartPorts(
            InlineThreadManager(),
            lambda _venue: MarketDataCandleFeed(
                world.sync, world.history, world.stream, world.market
            ),
            BotTickFeed(MemoryEventBus(), MarketType.SPOT),
            RecordingNotifier(),
            preference,
        )
    )
    bot = BotSnapshot.of(stored("a00001", BotLifecycleState.DRAFT).bot, None)
    card = host.show(bot)
    assert isinstance(card, ChartCard)
    readouts: list[str] = []
    card.crosshair._on_readout = readouts.append
    yield _Open(host, card, preference, readouts)
    host.close()


def test_the_chart_opens_in_utc_until_the_owner_chooses_another_zone(opened) -> None:
    assert opened.axis_zone() == service.DEFAULT_TIMEZONE
    assert "2026-10-19 12:01:30" in opened.crosshair_time()


def test_the_chart_under_system_shows_the_machines_local_time_not_utc(opened) -> None:
    opened.preference.set_zone(service.SYSTEM_TIMEZONE_KEY)

    assert opened.axis_zone() == service.SYSTEM_TIMEZONE_KEY
    assert "2026-10-19 19:01:30" in opened.crosshair_time()


def test_a_chart_built_after_the_choice_opens_in_the_chosen_zone(opened) -> None:
    opened.preference.set_zone(service.SYSTEM_TIMEZONE_KEY)
    other = BotSnapshot.of(stored("a00002", BotLifecycleState.DRAFT).bot, None)

    card = opened.host.show(other)

    assert isinstance(card, ChartCard)
    axis = card.plot_layout.main_plot.getAxis("bottom")
    assert axis.display_zone == service.SYSTEM_TIMEZONE_KEY


def test_an_iana_zone_is_followed_too(opened) -> None:
    opened.preference.set_zone("Asia/Tokyo")

    assert opened.axis_zone() == "Asia/Tokyo"
    assert "2026-10-19 21:01:30" in opened.crosshair_time()


def test_the_chart_header_holds_a_selector_that_writes_the_shared_zone(opened) -> None:
    combo = opened.card.findChild(DisplayTimezoneCombo, "cmbDisplayTimezone")
    assert combo is not None

    combo.activated.emit(combo.findData("Asia/Tokyo"))

    assert opened.preference.zone == "Asia/Tokyo"
    assert opened.axis_zone() == "Asia/Tokyo"
