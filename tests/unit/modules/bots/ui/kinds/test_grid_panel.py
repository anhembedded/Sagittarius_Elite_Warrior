"""`EPIC-029F` — the Grid's editor: the user's fields, suggestions only on a click."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
    SuggestedRange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    PARAMETERS_WITHOUT_A_DEFAULT,
    unset_parameters,
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
