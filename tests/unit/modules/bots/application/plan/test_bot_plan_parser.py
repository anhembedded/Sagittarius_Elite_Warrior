"""`EPIC-038I` - a plan file is read strictly: a person reviews it, a machine applies it.

A plan names bots, never a key: an unknown field is a mistake to refuse, not to
ignore, and the refusal must not echo the value it refused (it may be a secret).
"""

from __future__ import annotations

import json

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    SCHEMA,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_parser import (
    InvalidBotPlanError,
    parse_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    StubKind,
)

CATALOG = BotKindCatalog([StubKind("grid")])


def _bot(**overrides: object) -> dict[str, object]:
    bot: dict[str, object] = {
        "name": "BTC grid",
        "kind": "grid",
        "venue": "spot_testnet",
        "symbol": "btcusdt",
        "params": {"lower": "60000", "upper": "70000"},
        "desired_state": "running",
    }
    bot.update(overrides)
    return bot


def _plan(*bots: dict[str, object], **top: object) -> str:
    return json.dumps({"schema": SCHEMA, "bots": list(bots), **top})


def _problems(text: str) -> tuple[str, ...]:
    with pytest.raises(InvalidBotPlanError) as raised:
        parse_plan(text, CATALOG)
    return raised.value.problems


def test_a_valid_plan_is_read_into_typed_bots() -> None:
    document = parse_plan(_plan(_bot()), CATALOG)

    (bot,) = document.bots
    assert bot.name == "BTC grid" and bot.kind == "grid"
    assert bot.venue is TradingVenue.SPOT_TESTNET
    assert bot.symbol == "BTCUSDT", "the symbol is stored upper-case, as create does"
    assert dict(bot.params) == {"lower": "60000", "upper": "70000"}
    assert bot.desired_state is DesiredState.RUNNING


def test_an_empty_plan_is_valid_and_wants_nothing() -> None:
    assert parse_plan(_plan(), CATALOG).bots == ()


@pytest.mark.parametrize("field", ["api_key", "secret", "api_secret", "account_id"])
def test_a_plan_with_a_key_or_account_field_is_rejected_without_echoing_its_value(
    field: str,
) -> None:
    planted = "SECRET-SENTINEL-do-not-print"

    problems = _problems(_plan(_bot(**{field: planted})))

    assert any(field in p and "unknown field" in p for p in problems), problems
    assert all(planted not in p for p in problems), "the refusal repeated the value"


def test_a_secret_at_the_top_level_is_rejected_too() -> None:
    problems = _problems(_plan(_bot(), api_key="SECRET-SENTINEL-do-not-print"))

    assert any("api_key" in p for p in problems)
    assert all("SECRET-SENTINEL" not in p for p in problems)


@pytest.mark.parametrize("name", ["api_key", "API_SECRET", "binance_token", "password"])
def test_a_parameter_named_like_a_secret_is_rejected(name: str) -> None:
    problems = _problems(_plan(_bot(params={"lower": "1", name: "x"})))

    assert any(name in p and "secret" in p.lower() for p in problems), problems


def test_every_problem_is_listed_with_where_it_is() -> None:
    problems = _problems(
        _plan(
            _bot(kind="martingale"),
            _bot(name="second", venue="moon_testnet"),
            _bot(name="third", desired_state="paused"),
        )
    )

    joined = "\n".join(problems)
    assert "bots[0]" in joined and "martingale" in joined and "grid" in joined
    assert "bots[1]" in joined and "moon_testnet" in joined
    assert "bots[2]" in joined and "desired_state" in joined


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ("not json at all", "not valid JSON"),
        ("[]", "JSON object"),
        (json.dumps({"bots": []}), "schema"),
        (json.dumps({"schema": "sew.bot-plan/2", "bots": []}), "sew.bot-plan/2"),
        (json.dumps({"schema": SCHEMA}), "bots"),
        (json.dumps({"schema": SCHEMA, "bots": {}}), "bots"),
    ],
    ids=[
        "not json",
        "not an object",
        "no schema",
        "a later schema",
        "no bots",
        "bots not a list",
    ],
)
def test_a_file_that_is_not_a_plan_says_why(text: str, needle: str) -> None:
    assert any(needle in p for p in _problems(text))


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"name": 3},
        {"symbol": " "},
        {"params": ["lower"]},
        {"params": {"lower": 1}},
        {"params": {"": "1"}},
        {"desired_state": None},
    ],
    ids=[
        "empty name",
        "name not text",
        "blank symbol",
        "params a list",
        "param a number",
        "empty param name",
        "no desired state",
    ],
)
def test_a_field_of_the_wrong_shape_is_refused(overrides: dict[str, object]) -> None:
    assert _problems(_plan(_bot(**overrides)))


def test_a_missing_field_is_named() -> None:
    bot = _bot()
    del bot["desired_state"]

    assert any("desired_state" in p and "missing" in p for p in _problems(_plan(bot)))


def test_two_entries_with_one_name_and_venue_are_refused_but_one_name_on_two_venues_is_fine() -> (
    None
):
    assert any(
        "twice" in p or "duplicate" in p.lower()
        for p in _problems(_plan(_bot(), _bot(symbol="ETHUSDT")))
    )

    document = parse_plan(_plan(_bot(), _bot(venue="spot_mainnet")), CATALOG)
    assert len(document.bots) == 2


def test_a_new_kind_in_the_catalog_needs_no_change_in_the_plan_code() -> None:
    catalog = BotKindCatalog([StubKind("grid"), StubKind("dca")])

    document = parse_plan(_plan(_bot(kind="dca")), catalog)

    assert document.bots[0].kind == "dca"


def test_the_numbers_stay_text_so_no_float_touches_a_price() -> None:
    with pytest.raises(InvalidBotPlanError) as raised:
        parse_plan(_plan(_bot(params={"lower": 60000.1})), CATALOG)

    assert any("text" in p and "lower" in p for p in raised.value.problems)
