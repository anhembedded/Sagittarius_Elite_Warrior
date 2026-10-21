"""`EPIC-043D` — a desk's headline says its account's few key figures once more above the detail,
from the summary it shows and the positions its table holds, never from a second read."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from PySide6.QtGui import QGuiApplication
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_closed_event import (
    PositionClosedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_summary.summary_lines import (
    summary_readout,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_headline import (
    EQUITY_KEY,
    LIQUIDATION_KEY,
    PNL_KEY,
    POSITIONS_KEY,
    headline_figures,
    liquidation_distance_percent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    build_position_row,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)

from .account_tabs_fixtures import position
from .desk_screen_fixtures import DeskWorld, build_desk

_FUTURES = TradingVenue.FUTURES_TESTNET


def _futures(pnl: str = "12.5", mode: AssetMode = AssetMode.SINGLE_ASSET):
    return FuturesAccountSummary(
        venue=_FUTURES,
        available_balance=Decimal(100),
        equity=Decimal("1234.5"),
        wallet_balance=Decimal(1222),
        margin_balance=Decimal("1234.5"),
        unrealized_pnl=Decimal(pnl),
        position_mode=PositionMode.ONE_WAY,
        asset_mode=mode,
    )


def _spot(equity: str | None = "500"):
    return SpotAccountSummary(
        venue=TradingVenue.SPOT_TESTNET,
        available_balance=Decimal(50),
        equity=Decimal(equity) if equity is not None else None,
        quote_asset="USDT",
        quote_free=Decimal(50),
        quote_locked=Decimal(7),
    )


def _row(
    symbol: str = "BTCUSDT", mark: str = "60000", liquidation: str | None = "54000"
):
    return build_position_row(
        replace(
            position(symbol),
            mark_price=Decimal(mark),
            liquidation_price=Decimal(liquidation) if liquidation else None,
        )
    )


def _texts(figures) -> dict[str, str]:
    return {figure.key: figure.text for figure in figures}


# -- the figures ---------------------------------------------------------------------------


def test_an_unread_account_has_no_headline() -> None:
    assert headline_figures(None, ()) == ()


def test_a_futures_headline_is_value_pnl_positions_and_the_nearest_liquidation() -> (
    None
):
    figures = headline_figures(
        _futures(), (_row("BTCUSDT"), _row("ETHUSDT", "3000", "2850"))
    )

    assert [figure.key for figure in figures] == [
        EQUITY_KEY,
        PNL_KEY,
        POSITIONS_KEY,
        LIQUIDATION_KEY,
    ]
    assert _texts(figures) == {
        EQUITY_KEY: "1,234.50",
        PNL_KEY: "▲ +12.50",
        POSITIONS_KEY: "2",
        LIQUIDATION_KEY: "5.00%",
    }


def test_the_captions_name_the_unit_of_the_account(qapp) -> None:
    usdt = {f.key: f.caption for f in headline_figures(_futures(), ())}
    usd = {
        f.key: f.caption
        for f in headline_figures(_futures(mode=AssetMode.MULTI_ASSETS), ())
    }

    assert usdt[EQUITY_KEY] == "Margin balance (USDT)"
    assert usdt[PNL_KEY] == "Unrealized PnL (USDT)"
    assert usd[EQUITY_KEY] == "Margin balance (USD)"


@pytest.mark.parametrize(
    ("pnl", "arrow", "tone"),
    [
        ("12.5", "▲", Tone.POSITIVE),
        ("-3", "▼", Tone.NEGATIVE),
        ("0", "", Tone.NEUTRAL),
    ],
    ids=["profit", "loss", "zero"],
)
def test_the_pnl_says_its_direction_in_words_and_in_tone(pnl, arrow, tone) -> None:
    figure = next(f for f in headline_figures(_futures(pnl), ()) if f.key == PNL_KEY)

    assert figure.text.startswith(arrow)
    assert figure.tone is tone


def test_a_spot_headline_is_its_account_value_alone() -> None:
    figures = headline_figures(_spot(), ())

    assert _texts(figures) == {EQUITY_KEY: "500.00"}
    assert figures[0].caption == "Account value (USDT)"


def test_the_headline_names_its_equity_as_the_summary_beside_it_does() -> None:
    """One number, one name: the summary calls Futures' Margin balance and Spot's Account value."""
    for summary in (_futures(), _spot()):
        panel = {spec.title for spec in summary_readout(summary).specs}
        caption = headline_figures(summary, ())[0].caption

        assert caption in panel


def test_a_spot_value_that_cannot_be_priced_says_unknown_never_a_number() -> None:
    assert _texts(headline_figures(_spot(None), ())) == {EQUITY_KEY: "unknown"}


def test_no_open_position_says_none_and_counts_zero() -> None:
    texts = _texts(headline_figures(_futures(), ()))

    assert texts[POSITIONS_KEY] == "0"
    assert texts[LIQUIDATION_KEY] == "none"


def test_a_position_the_exchange_gave_no_liquidation_price_has_no_distance() -> None:
    texts = _texts(headline_figures(_futures(), (_row(liquidation=None),)))

    assert texts[POSITIONS_KEY] == "1"
    assert texts[LIQUIDATION_KEY] == "none"


@pytest.mark.parametrize(
    ("mark", "liquidation", "expected"),
    [
        ("60000", "54000", 10.0),
        ("60000", "66000", 10.0),
        ("100", "99", 1.0),
        ("100", "50", 50.0),
    ],
    ids=["long", "short", "near", "far"],
)
def test_the_distance_is_the_share_of_the_mark_between_it_and_the_exchanges_price(
    mark, liquidation, expected
) -> None:
    distance = liquidation_distance_percent((_row(mark=mark, liquidation=liquidation),))

    assert distance == pytest.approx(expected)


def test_the_nearest_of_several_positions_is_the_distance_shown() -> None:
    rows = (
        _row("BTCUSDT", "100", "50"),
        _row("ETHUSDT", "100", "95"),
        _row("SOLUSDT", "100", "80"),
    )

    assert liquidation_distance_percent(rows) == pytest.approx(5.0)


# -- the wiring: what the desk shows is what the headline says -------------------------------


def _headline_text(desk, key: str) -> str | None:
    return desk.view.headline.text_of(key)


def test_the_headline_is_hidden_until_the_account_is_read(qtbot) -> None:
    desk = build_desk(qtbot, _FUTURES)

    assert desk.view.headline.isHidden()


def test_a_summary_the_desk_shows_is_in_its_headline_with_the_pnls_tone(
    qtbot, qapp
) -> None:
    world = DeskWorld()
    desk = build_desk(qtbot, _FUTURES, world)

    world.bus.emit(AccountSummaryChangedEvent(summary=_futures()))
    qapp.processEvents()

    assert _headline_text(desk, EQUITY_KEY) == "1,234.50"
    assert _headline_text(desk, PNL_KEY) == "▲ +12.50"
    label = desk.view.headline.cell_value(PNL_KEY)
    toned = label.palette().color(label.foregroundRole())
    assert toned == tone_colour(Tone.POSITIVE, QGuiApplication.palette())


def test_a_position_that_reaches_the_table_reaches_the_headline_and_leaving_removes_it(
    qtbot, qapp
) -> None:
    world = DeskWorld()
    desk = build_desk(qtbot, _FUTURES, world)
    world.bus.emit(AccountSummaryChangedEvent(summary=_futures()))
    qapp.processEvents()
    assert _headline_text(desk, POSITIONS_KEY) == "0"

    held = replace(
        position("BTCUSDT"), mark_price=Decimal(100), liquidation_price=Decimal(90)
    )
    world.bus.emit(PositionChangedEvent(position=held, venue=_FUTURES))
    qapp.processEvents()
    assert _headline_text(desk, POSITIONS_KEY) == "1"
    assert _headline_text(desk, LIQUIDATION_KEY) == "10.00%"

    world.bus.emit(PositionClosedEvent(symbol="BTCUSDT", venue=_FUTURES))
    qapp.processEvents()
    assert _headline_text(desk, POSITIONS_KEY) == "0"
    assert _headline_text(desk, LIQUIDATION_KEY) == "none"


def test_a_spot_desk_shows_its_account_value_alone(qtbot, qapp) -> None:
    world = DeskWorld()
    desk = build_desk(qtbot, TradingVenue.SPOT_TESTNET, world)

    world.bus.emit(AccountSummaryChangedEvent(summary=_spot()))
    qapp.processEvents()

    assert desk.view.headline.keys == (EQUITY_KEY,)
    assert _headline_text(desk, EQUITY_KEY) == "500.00"


def test_the_headline_is_above_the_detail_in_the_desks_header(qtbot) -> None:
    desk = build_desk(qtbot, _FUTURES)
    bar = desk.view.findChild(type(desk.view.headline.parent()), "deskContextBar")

    assert bar is not None
    assert desk.view.headline.parent() is bar


def test_a_position_with_no_mark_has_no_distance_and_never_divides_by_zero() -> None:
    assert liquidation_distance_percent((_row(mark="0", liquidation="90"),)) is None
    nearest = liquidation_distance_percent(
        (_row("BTCUSDT", mark="0", liquidation="90"), _row("ETHUSDT", "100", "90"))
    )

    assert nearest == pytest.approx(10.0)


# -- freshness: the headline never looks current while the summary says it is not ------------


def test_a_summary_gone_stale_says_so_in_the_headline_and_keeps_the_last_figures(
    qtbot, qapp
) -> None:
    world = DeskWorld()
    desk = build_desk(qtbot, _FUTURES, world)
    world.bus.emit(AccountSummaryChangedEvent(summary=_futures()))
    qapp.processEvents()
    assert desk.view.headline.stale_text == ""

    world.bus.emit(
        AccountSummaryStaleEvent(reason="the venue timed out", venue=_FUTURES)
    )
    qapp.processEvents()

    assert desk.view.account_summary.stale_text == "Out of date: the venue timed out"
    assert desk.view.headline.stale_text == "Out of date: the venue timed out"
    assert _headline_text(desk, EQUITY_KEY) == "1,234.50"


def test_the_next_summary_clears_the_headlines_mark(qtbot, qapp) -> None:
    world = DeskWorld()
    desk = build_desk(qtbot, _FUTURES, world)
    world.bus.emit(AccountSummaryChangedEvent(summary=_futures()))
    world.bus.emit(AccountSummaryStaleEvent(reason="down", venue=_FUTURES))
    qapp.processEvents()
    assert desk.view.headline.stale_text != ""

    world.bus.emit(AccountSummaryChangedEvent(summary=_futures("80")))
    qapp.processEvents()

    assert desk.view.headline.stale_text == ""
    assert desk.view.account_summary.stale_text == ""
