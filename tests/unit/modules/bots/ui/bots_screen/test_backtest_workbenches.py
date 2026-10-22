"""`BUG-172`, `EPIC-040E` — the Backtest tab shows the workbench of the selected bot's venue.

@details A workbench's chart and sync read the market the bot's orders fill in, so two bots on two
venues must not share one (and so a sync): a bot of another venue gets that venue's workbench, a bot
of the same venue keeps the one it has. The tab says why it is off, and is never hidden, for a bot
whose kind has no backtest or whose venue the kind does not trade on."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_stored_candles import (
    StoredCandles,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_kind_backtester import (
    IKindBacktester,
    KindBacktestRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    plan_market_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_answer import (
    BacktestAnswer,
    BacktestCancelled,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench import (
    BacktestWorkbench,
    WorkbenchPorts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.backtest_workbenches import (
    BacktestWorkbenches,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    NO_BACKTEST_TEXT,
    NO_SELECTION_BACKTEST_TEXT,
    BotsView,
    TabAvailability,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_panels import panel_for
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    StubKind,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.futures_replay_builders import (
    BRACKETS,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.backtest.sandbox_fixtures import (
    market as sandbox_market,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.chart.bot_chart_fixtures import (
    InlineThreadManager,
)

from .bots_screen_fixtures import stored

_TESTNET = TradingVenue.SPOT_TESTNET
_MAINNET = TradingVenue.SPOT_MAINNET
_FUTURES = TradingVenue.FUTURES_TESTNET


class _Cancelled(IKindBacktester):
    def run(self, request: KindBacktestRequest) -> BacktestAnswer:
        return BacktestCancelled(0, 0)


class _SpotOnly(StubKind):
    """A kind with a backtest that trades on Spot only."""

    def __init__(self) -> None:
        super().__init__("spot_only")

    def backtester(self) -> IKindBacktester:
        return _Cancelled()


class _RecordingView(BotsView):
    """The real view, remembering each page it was given and each state of its tab."""

    def __init__(self) -> None:
        # Before the view builds itself: it shows its own instruction first.
        self.pages: list[tuple[QWidget | None, str]] = []
        self.tabs: list[TabAvailability] = []
        super().__init__()
        self.pages.clear()

    def set_backtest_page(self, page: QWidget | None, note: str) -> None:
        self.pages.append((page, note))
        super().set_backtest_page(page, note)

    def set_backtest_available(self, tab: TabAvailability) -> None:
        self.tabs.append(tab)
        super().set_backtest_available(tab)


class _Host:
    """A host over a catalog of the Grid (with its backtest), a kind with none and a Spot-only kind,
    recording every workbench built, every page shown and every tab state."""

    def __init__(self) -> None:
        sources = FakeMarketDataSources()
        for venue in (_TESTNET, _MAINNET, _FUTURES):
            sources.serving(FakeMarketDataSources.ports(venue.market_data_venue))
        self.built: list[WorkbenchPorts] = []
        self.view = _RecordingView()
        self.pages = self.view.pages
        self.tabs = self.view.tabs
        self._sources = sources
        catalog = BotKindCatalog(
            [
                GridKind(None, GridThresholds(), _Cancelled()),  # type: ignore[arg-type]
                StubKind("no_backtest"),
                _SpotOnly(),
            ]
        )
        self.host = BacktestWorkbenches(self._ports_for, catalog, self.view)
        self._catalog = catalog

    def _ports_for(self, venue: TradingVenue) -> WorkbenchPorts:
        ports = self._sources.ports_for(venue.market_data_venue)
        market = plan_market_of(venue)
        made = WorkbenchPorts(
            InlineThreadManager(),
            lambda query: BacktestCancelled(0, 0),
            ports.sync,
            MarketDataCandleFeed(ports.sync, ports.history, ports.stream, market),
            RecordingNotifier(),
            self._catalog.kind,
            panel_for,
            DisplayTimezonePreference(),
            lambda query: StoredCandles((), 0, 0, 1),
            market,
        )
        self.built.append(made)
        return made

    def follow(
        self,
        bot_id: str,
        venue: TradingVenue,
        kind: str = "grid",
        *,
        market: PlannerMarket | None = None,
        risk: PlanRiskFacts | None = None,
    ) -> None:
        snapshot = replace(
            BotSnapshot.of(stored(bot_id, BotLifecycleState.DRAFT).bot, None),
            venue=venue,
            kind=kind,
        )
        self.host.follow(SimpleNamespace(bot=snapshot, market=market, risk=risk))  # type: ignore[arg-type]


@pytest.fixture
def host(qapp):  # type: ignore[no-untyped-def]
    made = _Host()
    yield made
    made.host.close()


def test_a_workbench_is_built_per_venue_and_kept_for_the_same_venue(
    host: _Host,
) -> None:
    host.follow("a00001", _TESTNET)
    host.follow("a00002", _TESTNET)
    assert [ports.market for ports in host.built] == [MarketType.SPOT]

    host.follow("a00003", _MAINNET)

    assert len(host.built) == 2
    pages = [page for page, _ in host.pages if page is not None]
    assert len(pages) == 2 and pages[0] is not pages[1]


def test_going_back_to_a_venue_shows_the_workbench_it_had(host: _Host) -> None:
    """Its sandbox, with any edits, was never closed: the discard question is the workbench's."""
    host.follow("a00001", _TESTNET)
    host.follow("a00003", _MAINNET)
    host.follow("a00002", _TESTNET)

    pages = [page for page, _ in host.pages if page is not None]
    assert len(host.built) == 2
    assert pages[0] is pages[2] and pages[0] is not pages[1]


def test_a_futures_bot_gets_a_workbench_in_its_own_market(host: _Host) -> None:
    """`EPIC-039J` — the Futures backtest exists (`EPIC-039K`)."""
    host.follow("a00005", _FUTURES)

    assert [ports.market for ports in host.built] == [MarketType.FUTURES_USD_M]
    assert host.tabs[-1] == TabAvailability()


def test_no_selection_leaves_an_instruction_and_the_tab_on(host: _Host) -> None:
    host.host.follow(SimpleNamespace(bot=None, market=None, risk=None))  # type: ignore[arg-type]

    assert host.pages == [(None, NO_SELECTION_BACKTEST_TEXT)]
    assert host.tabs == [TabAvailability()]
    assert host.built == []


def test_a_kind_with_no_backtest_turns_the_tab_off_and_says_why(host: _Host) -> None:
    host.follow("a00001", _TESTNET, kind="no_backtest")

    assert host.tabs == [TabAvailability(False, NO_BACKTEST_TEXT)]
    assert host.pages == [(None, NO_BACKTEST_TEXT)]
    assert host.built == []


def test_a_venue_the_kind_does_not_trade_on_turns_the_tab_off_and_says_which(
    host: _Host,
) -> None:
    host.follow("a00001", _FUTURES, kind="spot_only")

    reason = "The spot_only backtest does not replay Futures Testnet."
    assert host.tabs == [TabAvailability(False, reason)]
    assert host.pages == [(None, reason)]


def test_a_kind_nobody_registered_is_told_as_no_backtest(host: _Host) -> None:
    host.follow("a00001", _TESTNET, kind="forgotten")

    assert host.tabs == [TabAvailability(False, NO_BACKTEST_TEXT)]


def test_the_tab_comes_back_on_for_a_bot_that_can_be_backtested(host: _Host) -> None:
    host.follow("a00001", _TESTNET, kind="no_backtest")
    host.follow("a00002", _TESTNET)

    assert [tab.enabled for tab in host.tabs] == [False, True]
    assert host.pages[-1][0] is not None


def _futures_facts() -> tuple[PlannerMarket, PlanRiskFacts]:
    facts = PlanRiskFacts(
        FuturesSymbolSetting("BTCUSDT", 3, MarginType.ISOLATED, Decimal(10**9)),
        BRACKETS,
    )
    return sandbox_market(), facts


def test_the_workbench_is_followed_with_the_bots_market_and_risk_facts(
    host: _Host,
) -> None:
    """Run is off until the symbol's terms and, on a position venue, its leverage brackets are
    read: both come from the selection, so dropping either leaves Run off."""
    planner, facts = _futures_facts()

    host.follow("a00001", _FUTURES)
    page = host.pages[-1][0]
    assert isinstance(page, BacktestWorkbenchView)
    assert (
        page.run_button.toolTip()
        == "The market numbers for this symbol are still being read."
    )

    host.follow("a00001", _FUTURES, market=planner)
    assert "leverage brackets" in page.run_button.toolTip()

    host.follow("a00001", _FUTURES, market=planner, risk=facts)
    assert page.run_button.isEnabled() and page.run_button.toolTip() == ""


def test_the_workbench_comes_back_for_the_same_venue_after_a_note(host: _Host) -> None:
    """A page replaced by a note is put back when the next bot can be backtested, even on the
    venue the page was last shown for."""
    host.follow("a00001", _TESTNET)
    page = host.pages[-1][0]
    host.follow("a00002", _TESTNET, kind="no_backtest")
    assert host.pages[-1][0] is None

    host.follow("a00003", _TESTNET)

    assert host.pages[-1][0] is page


def test_close_shuts_every_workbench_and_a_second_close_is_harmless(
    host: _Host, monkeypatch: pytest.MonkeyPatch
) -> None:
    host.follow("a00001", _TESTNET)
    host.follow("a00003", _MAINNET)
    shut: list[BacktestWorkbench] = []
    real = BacktestWorkbench.shutdown

    def record(workbench: BacktestWorkbench) -> None:
        shut.append(workbench)
        real(workbench)

    monkeypatch.setattr(BacktestWorkbench, "shutdown", record)

    host.host.close()
    host.host.close()

    assert len(shut) == 2  # each kept workbench once; a second close finds none
    host.follow("a00004", _TESTNET)
    assert len(host.built) == 3  # a closed venue is built again, not reused
