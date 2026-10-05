"""`EPIC-028J` — a desk's summary panel shows its market's own figures, is
read once when the desk opens, and is then kept by its venue's events,
marked stale with a reason and cleared by the next change."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AssetMode,
    FuturesAccountSummary,
    SpotAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.account_summary_changed_event import (
    AccountSummaryChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.account_summary_stale_event import (
    AccountSummaryStaleEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_activity import (
    FakeAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_summary.account_summary_panel import (
    AccountSummaryPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_summary.account_summary_presenter import (
    AccountSummaryPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_summary.summary_lines import (
    summary_readout,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_feed import OrderFeed
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)

from .order_entry_fixtures import HeldThreadManager, InlineThreadManager

_FUTURES = TradingVenue.FUTURES_TESTNET


def _futures(available: str = "100", mode: AssetMode = AssetMode.SINGLE_ASSET):
    return FuturesAccountSummary(
        venue=_FUTURES,
        available_balance=Decimal(available),
        equity=Decimal(120),
        wallet_balance=Decimal(125),
        margin_balance=Decimal(120),
        unrealized_pnl=Decimal(-5),
        position_mode=PositionMode.ONE_WAY,
        asset_mode=mode,
    )


# -- the lines ------------------------------------------------------------- #


def _shown(qtbot, summary) -> dict[str, str | None]:
    """What the panel shows for `summary`: each row's title and its text."""
    panel = AccountSummaryPanel()
    qtbot.addWidget(panel)
    readout = summary_readout(summary)
    panel.show_readout(readout)
    if readout is None:
        return {}
    return {spec.title: panel.value_of(spec.key) for spec in readout.specs}


def test_a_futures_account_shows_its_four_figures_in_usdt(qtbot) -> None:
    assert _shown(qtbot, _futures()) == {
        "Available (USDT)": "100.00",
        "Wallet balance (USDT)": "125.00",
        "Unrealized PnL (USDT)": "-5.00",
        "Margin balance (USDT)": "120.00",
    }


def test_a_multi_assets_account_counts_in_usd_and_says_so(qtbot) -> None:
    shown = _shown(qtbot, _futures(mode=AssetMode.MULTI_ASSETS))

    assert shown["Available (USD)"] == "100.00"
    assert shown["Margin"] == "every margin asset (Multi-Assets)"


def test_a_spot_account_whose_value_is_unknown_says_so(qtbot) -> None:
    shown = _shown(
        qtbot,
        SpotAccountSummary(
            venue=TradingVenue.SPOT_TESTNET,
            available_balance=Decimal(50),
            equity=None,
            quote_asset="USDT",
            quote_free=Decimal(50),
            quote_locked=Decimal(7),
        ),
    )

    assert shown == {
        "Available (USDT)": "50.00",
        "In orders (USDT)": "7.00",
        "Account value": "unknown: a holding could not be priced",
    }


def test_an_unread_account_shows_no_figure(qtbot) -> None:
    panel = AccountSummaryPanel()
    qtbot.addWidget(panel)

    panel.show_readout(summary_readout(None))

    assert panel.value_of("available") is None
    assert not panel.findChild(QLabel, "lblAccountSummaryUnread").isHidden()


# -- the presenter --------------------------------------------------------- #


def _summary_desk(qtbot, threads=None):
    bus = MemoryEventBus()
    activity = FakeAccountActivity()
    panel = AccountSummaryPanel()
    qtbot.addWidget(panel)
    presenter = AccountSummaryPresenter(
        panel,
        activity,
        OrderFeed(bus, _FUTURES, parent=panel),
        threads or InlineThreadManager(),
    )
    return bus, activity, panel, presenter


def test_the_desk_reads_its_summary_when_it_opens(qtbot) -> None:
    _, activity, panel, presenter = _summary_desk(qtbot)
    activity.holding_summary(_futures("100"))

    presenter.refresh()

    assert panel.value_of("available") == "100.00"
    assert panel.stale_text == ""


def test_an_unreadable_account_is_marked_rather_than_shown_empty(qtbot) -> None:
    _, _, panel, presenter = _summary_desk(qtbot)

    presenter.refresh()

    assert panel.stale_text == "Out of date: the account could not be read"


def test_stale_is_marked_with_its_reason_and_cleared_by_the_next_change(
    qtbot, qapp
) -> None:
    bus, activity, panel, presenter = _summary_desk(qtbot)
    activity.holding_summary(_futures("100"))
    presenter.refresh()

    bus.emit(AccountSummaryStaleEvent(reason="the venue timed out", venue=_FUTURES))
    qapp.processEvents()
    assert panel.stale_text == "Out of date: the venue timed out"
    assert panel.value_of("available") == "100.00"

    bus.emit(AccountSummaryChangedEvent(summary=_futures("80")))
    qapp.processEvents()
    assert panel.stale_text == ""
    assert panel.value_of("available") == "80.00"


def test_another_venues_stale_mark_never_reaches_this_desk(qtbot, qapp) -> None:
    bus, activity, panel, presenter = _summary_desk(qtbot)
    activity.holding_summary(_futures())
    presenter.refresh()

    bus.emit(
        AccountSummaryStaleEvent(reason="spot down", venue=TradingVenue.SPOT_TESTNET)
    )
    qapp.processEvents()

    assert panel.stale_text == ""


def test_an_open_read_answering_after_a_newer_event_is_dropped(qtbot, qapp) -> None:
    held = HeldThreadManager()
    bus, activity, panel, presenter = _summary_desk(qtbot, held)
    activity.holding_summary(_futures("100"))
    presenter.refresh()

    bus.emit(AccountSummaryChangedEvent(summary=_futures("80")))
    qapp.processEvents()
    held.run(0)

    assert panel.value_of("available") == "80.00"
