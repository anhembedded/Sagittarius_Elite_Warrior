"""`BOT-150` — a Grid created with no parameters is refused with the ones to set named.

New bot asks only for the kind, venue and symbol, so a fresh draft carries no
parameters. Its verdict asks for them in the panel's words rather than
reporting a missing key.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    LAST_PRICE,
    TERMS,
    inputs,
)


def test_a_new_grid_without_parameters_asks_for_them_by_name() -> None:
    evaluation = evaluate_grid(
        BotKindInputs({}, TERMS, MarketView(LAST_PRICE, None)), GridThresholds()
    )

    assert [v.code for v in evaluation.verdicts] == ["PARAMETERS_NOT_SET"]
    assert evaluation.verdicts[0].refuses
    assert evaluation.plan is None
    reason = evaluation.verdicts[0].reason
    assert "lower price, upper price and capital" in reason
    assert "is missing" not in reason


def test_a_blank_parameter_is_named_as_not_set() -> None:
    evaluation = evaluate_grid(inputs(capital_quote="  "), GridThresholds())

    assert [v.code for v in evaluation.verdicts] == ["PARAMETERS_NOT_SET"]
    assert evaluation.verdicts[0].reason == "Set the capital."


def test_a_full_set_of_parameters_is_judged_by_the_checks() -> None:
    codes = {v.code for v in evaluate_grid(inputs(), GridThresholds()).verdicts}

    assert "PARAMETERS_NOT_SET" not in codes
