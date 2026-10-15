"""`EPIC-039J` — the Grid's editor shows the rows the venue profile lists.

@details The business promise: a Spot Grid's editor is what it always was (seven parameters,
no Futures row, no extra key in the definition); a Futures Grid's shows its direction, leverage,
the margin mode and the liquidation estimate, because its profile lists them, never because
the widget names a market."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    VenueProfile,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_liquidation import (
    NOT_ESTIMATED,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_panel import (
    GridPanel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

D = Decimal
_SPOT = venue_profile_of(TradingVenue.SPOT_TESTNET)
_FUTURES = venue_profile_of(TradingVenue.FUTURES_TESTNET)
_SPOT_KEYS = {
    "lower",
    "upper",
    "grid_count",
    "spacing",
    "capital_quote",
    "stop_loss",
    "take_profit",
}
_SAVED = {
    "lower": "60000",
    "upper": "70000",
    "grid_count": "12",
    "spacing": "GEOMETRIC",
    "capital_quote": "1000",
    "stop_loss": "percent:5",
    "take_profit": "price:75000",
}


def _panel(qtbot, profile: VenueProfile | None) -> GridPanel:
    panel = GridPanel()
    qtbot.addWidget(panel)
    if profile is not None:
        panel.set_profile(profile)
    return panel


def _shown(panel: GridPanel) -> dict[str, bool]:
    exposure = panel.exposure
    return {
        "direction": exposure.direction.isVisibleTo(panel),
        "leverage": exposure.leverage.isVisibleTo(panel),
        "margin": exposure.margin_mode.isVisibleTo(panel),
        "liquidation": exposure.liquidation.isVisibleTo(panel),
    }


def _estimate(side: str, price: str, gap: str = "1500") -> Verdict:
    return Verdict(
        VerdictSeverity.OK,
        "LIQUIDATION_ESTIMATE",
        "r",
        {
            "liquidation_price": D(price),
            "mark": D(65000),
            "exit_price": D(57000),
            "gap": D(gap),
        },
        subject=side,
    )


def test_a_spot_editor_shows_no_futures_row_and_writes_no_extra_key(qtbot) -> None:
    for profile in (_SPOT, None):
        panel = _panel(qtbot, profile)
        panel.set_config(_SAVED)

        assert not any(_shown(panel).values())
        assert panel.config() == _SAVED
        assert set(panel.config()) == _SPOT_KEYS


def test_a_futures_editor_shows_direction_leverage_margin_and_liquidation(
    qtbot,
) -> None:
    panel = _panel(qtbot, _FUTURES)

    assert all(_shown(panel).values())
    assert panel.exposure.margin_mode.text() == "Isolated"
    assert panel.exposure.liquidation.text() == NOT_ESTIMATED
    offered = [
        panel.exposure.direction.itemData(i)
        for i in range(panel.exposure.direction.count())
    ]
    assert offered == ["LONG", "SHORT", "NEUTRAL"]


def test_a_direction_a_bot_runs_is_listed_enabled_and_one_it_does_not_greyed_out(
    qtbot,
) -> None:
    """`EPIC-039I` review: a direction no bot runs yet is never selectable and then refused at
    Start (the pattern of a closed venue, `BUG-208`). All three run on Futures now, so the
    greyed-out case is a profile that offers a direction it does not run."""
    open_profile = _FUTURES
    closed_profile = replace(
        _FUTURES,
        bot_directions=frozenset({TradeDirection.LONG, TradeDirection.SHORT}),
    )

    def states(profile: VenueProfile) -> dict[str, tuple[bool, str]]:
        direction = _panel(qtbot, profile).exposure.direction
        model = direction.model()
        return {
            direction.itemData(i): (model.item(i).isEnabled(), model.item(i).toolTip())
            for i in range(direction.count())
        }

    assert all(enabled for enabled, _ in states(open_profile).values())
    closed = states(closed_profile)
    assert closed["LONG"] == (True, "")
    enabled, reason = closed["NEUTRAL"]
    assert not enabled
    assert "neutral grid cannot run on Futures yet" in reason


def test_a_new_futures_grid_starts_long_at_two_times_and_writes_both_keys(
    qtbot,
) -> None:
    panel = _panel(qtbot, _FUTURES)
    panel.set_config({})

    assert panel.config()["direction"] == "LONG"
    assert panel.config()["leverage"] == "2"


def test_a_saved_futures_definition_shows_its_own_direction_and_leverage(
    qtbot,
) -> None:
    panel = _panel(qtbot, _FUTURES)
    saved = {**_SAVED, "direction": "NEUTRAL", "leverage": "7"}

    panel.set_config(saved)

    assert panel.config() == saved


def test_a_row_appears_because_the_profile_lists_it_not_because_of_a_market(
    qtbot,
) -> None:
    long_only = replace(_FUTURES, directions=frozenset({TradeDirection.LONG}))

    panel = _panel(qtbot, long_only)

    assert _shown(panel)["direction"] is False
    assert _shown(panel)["leverage"] is True
    assert panel.config()["direction"] == "LONG"


def test_the_leverage_is_bounded_by_the_profile(qtbot) -> None:
    capped = replace(_FUTURES, max_leverage=20)

    panel = _panel(qtbot, capped)

    assert panel.exposure.leverage.maximum() == 20
    assert panel.exposure.leverage.minimum() == 1


def test_changing_the_direction_or_the_leverage_is_an_edit(qtbot) -> None:
    panel = _panel(qtbot, _FUTURES)
    panel.set_config(_SAVED)
    heard: list[dict[str, str]] = []
    panel.config_changed.connect(heard.append)

    panel.exposure.leverage.setValue(5)
    panel.exposure.direction.setCurrentIndex(1)
    panel.exposure.direction.activated.emit(1)

    assert heard[0]["leverage"] == "5"
    assert heard[-1]["direction"] == "SHORT"


def test_showing_a_saved_definition_is_not_an_edit(qtbot) -> None:
    panel = _panel(qtbot, _FUTURES)
    heard: list[object] = []
    panel.config_changed.connect(heard.append)

    panel.set_config({**_SAVED, "direction": "SHORT", "leverage": "9"})

    assert heard == []


def test_the_liquidation_row_says_estimate_and_neutral_shows_two(qtbot) -> None:
    panel = _panel(qtbot, _FUTURES)

    panel.show_verdicts(
        (_estimate("long", "55000"), _estimate("short", "74000", "2500"))
    )

    long_line, short_line = panel.exposure.liquidation.text().splitlines()
    assert long_line.startswith("Long:") and "(estimate)" in long_line
    assert short_line.startswith("Short:") and "(estimate)" in short_line
    assert "safe" not in panel.exposure.liquidation.text().lower()


def test_the_liquidation_row_names_the_distance_to_the_exit(qtbot) -> None:
    panel = _panel(qtbot, _FUTURES)

    panel.show_verdicts((_estimate("long", "55000", "2000"),))

    text = panel.exposure.liquidation.text()
    assert "2,000" in text and "before the exit at 57,000" in text


def test_a_refused_side_says_it_blocks_start_in_words(qtbot) -> None:
    panel = _panel(qtbot, _FUTURES)
    inside = Verdict(
        VerdictSeverity.REFUSED,
        "LIQUIDATION_INSIDE_RANGE",
        "r",
        {"liquidation_price": D(60500)},
        subject="long",
    )

    panel.show_verdicts((inside,))

    assert panel.exposure.liquidation.text().startswith("Blocks Start: Long:")


def test_with_no_estimate_the_row_says_so_rather_than_a_zero(qtbot) -> None:
    panel = _panel(qtbot, _FUTURES)
    panel.show_verdicts((_estimate("long", "55000"),))

    panel.show_verdicts(())

    assert panel.exposure.liquidation.text() == NOT_ESTIMATED


def test_a_leverage_verdict_marks_the_leverage_field(qtbot) -> None:
    panel = _panel(qtbot, _FUTURES)
    ceiling = Verdict(VerdictSeverity.REFUSED, "LEVERAGE_ABOVE_CEILING", "too high")

    panel.show_verdicts((ceiling,))

    assert "too high" in panel.field_error_text("leverage")
    assert panel.field_label("LEVERAGE_ABOVE_CEILING") == "Leverage"
    assert panel.focus_field("LEVERAGE_ABOVE_CEILING")


def _choose(panel: GridPanel, direction: str) -> None:
    panel.exposure.direction.setCurrentIndex(
        panel.exposure.direction.findData(direction)
    )


def test_a_neutral_grids_exit_verdict_marks_the_exit_of_the_side_it_names(
    qtbot,
) -> None:
    panel = _panel(qtbot, _FUTURES)
    _choose(panel, "NEUTRAL")
    needed = Verdict(
        VerdictSeverity.REFUSED, "STOP_LOSS_NEEDED", "no exit", subject="short"
    )

    panel.show_verdicts((needed,))

    assert panel.field_error_text("take_profit") != ""
    assert panel.field_error_text("stop_loss") == ""


def test_a_short_grids_loss_exit_is_its_stop_loss_above_the_range(qtbot) -> None:
    panel = _panel(qtbot, _FUTURES)
    _choose(panel, "SHORT")
    needed = Verdict(
        VerdictSeverity.REFUSED, "STOP_LOSS_NEEDED", "no exit", subject="short"
    )

    panel.show_verdicts((needed,))

    assert panel.field_error_text("stop_loss") != ""
    assert panel.field_error_text("take_profit") == ""
