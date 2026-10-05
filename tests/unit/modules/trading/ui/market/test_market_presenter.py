"""`MarketPresenter` (`EPIC-033H`): the Watchlist, the chart tabs and going
live on the user's open (`BUG-104`); Tools → Check connection is
`test_market_connection_check.py`."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    StreamOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_commands import (
    CLOSE_CHART,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_presenter import (
    WATCHLIST_STREAM_OWNER,
    MarketPresenter,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_20_script import (
    Ema20Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.rsi_14_script import (
    Rsi14Script,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.ui.market.market_fixtures import (
    candle,
    tick,
)

_SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT")


class _Binder(ICommandBinder):
    """Holds what the presenter binds, as the Engine's registry would."""

    def __init__(self) -> None:
        self.handlers: dict[str, object] = {}
        self.initially_enabled: dict[str, bool] = {}

    def bind(
        self,
        action_id,
        handler,
        *,
        enabled=None,
        checked=None,
        initially_enabled=True,
    ) -> None:
        self.handlers[action_id] = handler
        self.initially_enabled[action_id] = initially_enabled


class _RefusingStream(FakeMarketStream):
    def start(self, owner_id, market_type, symbols, interval) -> StreamOutcome:
        return StreamOutcome(success=False, message="Testnet unreachable.")


def _watchlist_text(presenter: MarketPresenter, symbol: str, key: str) -> str:
    model = presenter.view.watchlist
    for row in range(model.rowCount()):
        if model.rows[row].symbol == symbol:
            return str(model.data(model.index(row, model.column(key))))
    raise KeyError(symbol)


# -- the Watchlist and the stream ---------------------------------------------


def test_the_watchlist_lists_the_tracked_symbols(build):
    presenter = build()

    assert [row.symbol for row in presenter.view.watchlist.rows] == list(_SYMBOLS)


def test_a_restored_mode_opens_a_chart_from_history_and_streams_nothing(
    build, threads, feed
):
    """`BUG-104`: a launch that restores this mode opens no stream. The first
    chart still opens, from local history only (`BUG-107`)."""
    stream = FakeMarketStream()
    presenter = build(stream=stream)

    presenter.on_mode_shown(NavigationSource.RESTORE)
    threads.run_all()

    assert presenter.view.open_symbols == ("BTCUSDT",)
    assert stream.calls == []
    assert feed.started == []
    assert "not live" in presenter.view.stream.text()


def test_the_users_open_starts_the_watchlist_stream_and_the_chart_goes_live(
    build, threads, feed
):
    stream = FakeMarketStream()
    presenter = build(stream=stream)
    presenter.on_mode_shown(NavigationSource.RESTORE)

    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    threads.run_all()

    held = stream.held_by(WATCHLIST_STREAM_OWNER)
    assert held is not None
    assert held.symbols == _SYMBOLS
    assert held.market_type is MarketType.SPOT
    assert feed.started == ["market.BTCUSDT"]
    assert presenter.view.stream.text() == "Market data: live"


def test_a_stream_that_does_not_start_says_so(build):
    """SPEC-002 §4/§5: a refused start reads as a failure, never as "no tick
    yet"."""
    presenter = build(stream=_RefusingStream())

    presenter.on_mode_shown(NavigationSource.USER_INTENT)

    assert presenter.view.stream.text() == "Market data: failed to start"
    assert any(
        "Testnet unreachable." in entry.message for entry in presenter.view.log.entries
    )


def test_a_tick_updates_its_symbols_row(build, event_bus):
    presenter = build()

    event_bus.emit(tick(candle("ETHUSDT", 0, open_price=100.0)))
    QCoreApplication.processEvents()

    assert _watchlist_text(presenter, "ETHUSDT", "last_price") != ""
    assert presenter.view.watchlist.rows[1].percent_change == pytest.approx(1.0)


# -- the charts ------------------------------------------------------------------


def test_activating_a_symbol_opens_its_chart_and_again_brings_it_forward(
    build, threads
):
    presenter = build()
    presenter.on_mode_shown(NavigationSource.RESTORE)

    presenter.view.symbol_opened.emit("ETHUSDT")
    presenter.view.symbol_opened.emit("BTCUSDT")
    threads.run_all()

    assert presenter.view.open_symbols == ("BTCUSDT", "ETHUSDT")
    assert presenter.view.current_symbol == "BTCUSDT"


def test_a_chart_opened_while_live_goes_live(build, threads, feed):
    presenter = build()
    presenter.on_mode_shown(NavigationSource.USER_INTENT)

    presenter.view.symbol_opened.emit("ETHUSDT")
    threads.run_all()

    assert feed.started == ["market.BTCUSDT", "market.ETHUSDT"]


def test_closing_a_tab_releases_its_charts_stream(build, threads, feed):
    presenter = build()
    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    threads.run_all()
    feed.stopped.clear()

    presenter.view.chart_closed.emit("BTCUSDT")
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert presenter.view.open_symbols == ()
    assert feed.stopped == ["market.BTCUSDT"]
    assert presenter.charts == {}


def test_a_live_candle_reaches_the_chart_of_its_symbol(build, threads, event_bus):
    presenter = build()
    presenter.on_mode_shown(NavigationSource.RESTORE)
    threads.run_all()
    chart = presenter.charts["BTCUSDT"]
    chart.show_indicators(("ema_20",))
    before = next(iter(chart._runner.active["ema_20"].series.values()))[0][-1]

    event_bus.emit(tick(candle("BTCUSDT", 60)))
    QCoreApplication.processEvents()

    after = next(iter(chart._runner.active["ema_20"].series.values()))[0][-1]
    assert after > before


def test_the_checked_indicators_apply_to_every_open_chart(build, threads):
    presenter = build()
    presenter.on_mode_shown(NavigationSource.RESTORE)
    presenter.view.symbol_opened.emit("ETHUSDT")
    threads.run_all()

    presenter.view.indicators_changed.emit(("rsi_14",))

    for chart in presenter.charts.values():
        assert chart.indicators == ("rsi_14",)
        assert set(chart._runner.active) == {"rsi_14"}


def test_the_indicators_list_offers_every_script(build):
    presenter = build()

    titles = [
        presenter.view.indicators.item(row).text()
        for row in range(presenter.view.indicators.count())
    ]
    assert titles == [Ema20Script.title, Rsi14Script.title]


def test_close_chart_closes_the_tab_in_front_and_is_off_when_none_is_open(
    build, threads
):
    """File → Close chart: the keyboard's way to a tab's close button."""
    presenter = build()
    binder = _Binder()
    presenter.bind_commands(binder)
    seen: list[bool] = []
    presenter.closeChartEnabled.connect(seen.append)
    presenter.on_mode_shown(NavigationSource.RESTORE)
    presenter.view.symbol_opened.emit("ETHUSDT")
    threads.run_all()

    binder.handlers[CLOSE_CHART](False)
    assert presenter.view.open_symbols == ("BTCUSDT",)
    binder.handlers[CLOSE_CHART](False)

    assert presenter.view.open_symbols == ()
    assert binder.initially_enabled[CLOSE_CHART] is False
    assert seen == [True, True, True, False]
