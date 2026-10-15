"""`EPIC-029F` — the Grid's editor: the user's fields, suggestions only on a click."""

from __future__ import annotations

import logging
from dataclasses import replace
from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
    SuggestedRange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
    ExchangeTerms,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    PARAMETERS_WITHOUT_A_DEFAULT,
    unset_parameters,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_panel import (
    GridPanel,
)

_CONFIG = {
    "lower": "60000",
    "upper": "70000",
    "grid_count": "12",
    "spacing": "GEOMETRIC",
    "capital_quote": "1000",
    "stop_loss": "percent:5",
    "take_profit": "price:75000",
}
_TERMS = ExchangeTerms(
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.00001"),
    min_notional=Decimal(5),
    maker_fee=Decimal("0.001"),
    taker_fee=Decimal("0.001"),
    max_notional_per_order=Decimal(5000),
    max_open_orders=100,
)


def _market(
    atr: SuggestedRange | None, bollinger: SuggestedRange | None
) -> PlannerMarket:
    return PlannerMarket(
        _TERMS, MarketView(Decimal(65000), Decimal(2500)), atr, bollinger
    )


def test_the_fields_show_and_read_back_every_parameter(qtbot) -> None:
    panel = GridPanel()
    qtbot.addWidget(panel)

    panel.set_config(_CONFIG)

    assert panel.config() == _CONFIG


def test_a_new_grid_leaves_blank_exactly_the_parameters_without_a_default(
    qtbot,
) -> None:
    """`BOT-150`, PR #349 review: the domain names the parameters a new Grid
    lacks; the panel must start every other one at a value."""
    panel = GridPanel()
    qtbot.addWidget(panel)

    panel.set_config({})

    blank = {key for key, value in panel.config().items() if not value.strip()}
    assert blank == set(PARAMETERS_WITHOUT_A_DEFAULT)
    assert unset_parameters(panel.config()) == tuple(
        PARAMETERS_WITHOUT_A_DEFAULT.values()
    )


def test_showing_parameters_is_not_an_edit_but_typing_is(qtbot) -> None:
    panel = GridPanel()
    qtbot.addWidget(panel)
    heard: list[dict[str, str]] = []
    panel.config_changed.connect(heard.append)

    panel.set_config(_CONFIG)
    assert heard == []

    qtbot.keyClicks(panel.capital, "5")
    assert heard[-1]["capital_quote"] == "10005"


def test_every_way_of_setting_the_grid_count_is_an_edit(qtbot) -> None:
    """`BUG-193`: the arrows, the wheel and Up/Down raised neither `textEdited`
    nor `editingFinished`, so the screen kept the count it had."""
    panel = GridPanel()
    qtbot.addWidget(panel)
    panel.set_config({**_CONFIG, "grid_count": "10"})
    heard: list[dict[str, str]] = []
    panel.config_changed.connect(heard.append)

    qtbot.keyClick(panel.grid_count, Qt.Key.Key_Down)
    assert heard[-1]["grid_count"] == "9"

    panel.grid_count.stepBy(-4)
    assert heard[-1]["grid_count"] == "5"

    panel.grid_count.lineEdit().selectAll()
    qtbot.keyClicks(panel.grid_count, "7")
    assert heard[-1]["grid_count"] == "7"


def test_an_exit_switched_off_reads_off_and_disables_its_value(qtbot) -> None:
    panel = GridPanel()
    qtbot.addWidget(panel)
    panel.set_config(_CONFIG)

    panel.stop_loss.kind.setCurrentIndex(panel.stop_loss.kind.findText("off"))
    panel.stop_loss.kind.activated.emit(panel.stop_loss.kind.currentIndex())

    assert panel.config()["stop_loss"] == "off"
    assert not panel.stop_loss.value.isEnabled()


def test_suggestions_wait_for_the_planner_and_fill_only_on_a_click(qtbot) -> None:
    panel = GridPanel()
    qtbot.addWidget(panel)
    panel.set_config(_CONFIG)
    assert not panel.suggest_atr.isEnabled()
    assert "daily candles" in panel.suggest_atr.toolTip()

    panel.set_planner_market(
        _market(SuggestedRange(Decimal("61234.567"), Decimal("68765.433")), None)
    )

    assert panel.config()["lower"] == "60000"  # nothing filled by itself
    assert panel.suggest_atr.isEnabled() and not panel.suggest_bollinger.isEnabled()
    heard: list[dict[str, str]] = []
    panel.config_changed.connect(heard.append)
    panel.suggest_atr.trigger()
    assert (panel.config()["lower"], panel.config()["upper"]) == (
        "61234.57",
        "68765.43",
    )
    assert heard[-1]["lower"] == "61234.57"


def test_a_read_only_panel_offers_no_edit_and_no_suggestion(qtbot) -> None:
    panel = GridPanel()
    qtbot.addWidget(panel)
    panel.set_planner_market(_market(SuggestedRange(Decimal(1), Decimal(2)), None))

    panel.set_editable(False)

    assert not panel.lower_price.isEnabled() and not panel.grid_count.isEnabled()
    assert not panel.suggest_atr.isEnabled()
    panel.set_editable(True)
    assert panel.suggest_atr.isEnabled()


def test_a_read_only_panel_offers_no_suggestion_when_the_planner_answers_late(
    qtbot,
) -> None:
    """A running Grid's editor is read-only from the moment it is shown; the
    planner's numbers arrive after that, and once re-offered the suggestion
    as if the fields could take it (found by `EPIC-033K` stage 2, when the
    Bots menu began to follow the action)."""
    panel = GridPanel()
    qtbot.addWidget(panel)
    panel.set_editable(False)

    panel.set_planner_market(_market(SuggestedRange(Decimal(1), Decimal(2)), None))

    assert not panel.suggest_atr.isEnabled()


def test_a_price_is_shown_without_the_zeros_the_exchange_pads_it_with(qtbot) -> None:
    """`BUG-210`: Binance publishes a tick of `0.01000000`; the suggested range was written
    `2371.98000000`, and a saved draft carried that text back into the field."""
    panel = GridPanel()
    qtbot.addWidget(panel)
    panel.set_planner_market(
        PlannerMarket(
            replace(_TERMS, tick_size=Decimal("0.01000000")),
            MarketView(Decimal(2500), Decimal(160)),
            SuggestedRange(Decimal("2371.9831"), Decimal("2824.1")),
            None,
        )
    )

    panel.suggest_atr.trigger()

    assert (panel.config()["lower"], panel.config()["upper"]) == ("2371.98", "2824.1")
    panel.set_config({**_CONFIG, "lower": "2371.98000000", "upper": "2824.11000000"})
    assert (panel.lower_price.text(), panel.upper_price.text()) == (
        "2371.98",
        "2824.11",
    )
    panel.set_config({**_CONFIG, "lower": "2400.00", "upper": "2800"})
    assert (panel.lower_price.text(), panel.upper_price.text()) == ("2400", "2800")


_OWNER_PRICE = Decimal("2368.155")
_OWNER_CONFIG = {
    "lower": "2000",
    "upper": "3000",
    "grid_count": "6",
    "spacing": "ARITHMETIC",
    "capital_quote": "35",
    "stop_loss": "price:2259",
    "take_profit": "price:2805",
}


def _owner_panel(qtbot, source: str, band: SuggestedRange) -> GridPanel:
    panel = GridPanel()
    qtbot.addWidget(panel)
    panel.set_config(_OWNER_CONFIG)
    market = _owner_panel_market()
    ranges = {"ATR": (band, None), "Bollinger": (None, band)}[source]
    panel.set_planner_market(PlannerMarket(_TERMS, market, *ranges))
    return panel


def _blocking(panel: GridPanel) -> list[str]:
    """What the planner says blocks Start for the fields as the panel now holds them."""
    market = _owner_panel_market()
    evaluation = evaluate_grid(
        BotKindInputs(panel.config(), _TERMS, market), GridThresholds()
    )
    return [verdict.code for verdict in evaluation.verdicts if verdict.refuses]


def _owner_panel_market() -> MarketView:
    return MarketView(_OWNER_PRICE, Decimal(160), base_asset="ETH", quote_asset="USDT")


@pytest.mark.parametrize(
    ("source", "band", "action"),
    [
        ("ATR", SuggestedRange(Decimal("2227.92"), Decimal("2515.54")), "suggest_atr"),
        (
            "Bollinger",
            SuggestedRange(Decimal(2370), Decimal("2825.29")),
            "suggest_bollinger",
        ),
    ],
)
def test_a_suggestion_writes_a_plan_that_start_does_not_refuse(
    qtbot, source: str, band: SuggestedRange, action: str
) -> None:
    """`BUG-211`: the owner's stop loss 2259 and take profit 2805 survived the new range."""
    panel = _owner_panel(qtbot, source, band)
    assert _blocking(panel)  # the plan as the owner had it is refused

    getattr(panel, action).trigger()

    assert _blocking(panel) == []
    config = panel.config()
    # The stop loss would block Start and moves; the take profit 2805 is valid (advice only)
    # and stays as the owner set it.
    assert config["stop_loss"] != "price:2259" and config["take_profit"] == "price:2805"
    assert Decimal(config["lower"]) <= _OWNER_PRICE <= Decimal(config["upper"])


def test_a_suggestion_says_which_exit_moved_and_the_note_goes_with_the_next_edit(
    qtbot,
) -> None:
    panel = _owner_panel(
        qtbot, "ATR", SuggestedRange(Decimal("2227.92"), Decimal("2515.54"))
    )

    panel.suggest_atr.trigger()

    note = panel.suggestion_note
    assert not note.isHidden()
    assert "stop loss moved from 2259 to 2105.38" in note.text()
    assert "take profit" not in note.text()
    panel.capital.textEdited.emit("40")
    assert note.isHidden()


def test_a_suggestion_leaves_an_off_exit_off(qtbot) -> None:
    panel = _owner_panel(
        qtbot, "ATR", SuggestedRange(Decimal("2227.92"), Decimal("2515.54"))
    )
    panel.stop_loss.show_encoded("off")

    panel.suggest_atr.trigger()

    assert panel.config()["stop_loss"] == "off"
    assert "stop loss" not in panel.suggestion_note.text()


def test_a_suggestion_is_logged_with_its_inputs_range_moves_and_readiness(
    qtbot, caplog: pytest.LogCaptureFixture
) -> None:
    panel = _owner_panel(
        qtbot, "Bollinger", SuggestedRange(Decimal(2370), Decimal("2825.29"))
    )

    with caplog.at_level(logging.INFO, logger="App.Bots.Grid"):
        panel.suggest_bollinger.trigger()

    lines = [r for r in caplog.records if "[grid-suggest]" in r.getMessage()]
    assert len(lines) == 1 and lines[0].levelno == logging.INFO
    text = lines[0].getMessage()
    for fragment in (
        "source=Bollinger",
        "band=2370-2825.29",
        "daily_atr=160",
        "last_price=2368.155",
        "tick=0.01",
        f"range={panel.config()['lower']}-{panel.config()['upper']}",
        "stop loss 2259->",
        "blocking=0",
    ):
        assert fragment in text
