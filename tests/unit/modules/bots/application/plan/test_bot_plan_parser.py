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
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
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


@pytest.mark.parametrize(
    "field", ["api_key", "client_secret", "api_secret", "account_id", "private_key"]
)
def test_a_plan_with_a_key_or_account_field_is_rejected_without_echoing_its_name_or_value(
    field: str,
) -> None:
    planted = "SECRET-SENTINEL-do-not-print"

    problems = _problems(_plan(_bot(**{field: planted})))

    assert any("bots[0]" in p and "unknown field" in p for p in problems), problems
    assert any("no key, secret or account identifier" in p for p in problems), (
        "a field named like a credential is told why"
    )
    joined = "\n".join(problems)
    assert planted not in joined, "the refusal repeated the value"
    assert field not in joined, (
        "the refusal repeated the field's name, which may be the secret"
    )


def test_a_secret_at_the_top_level_is_rejected_too() -> None:
    problems = _problems(_plan(_bot(), api_key="SECRET-SENTINEL-do-not-print"))

    assert any("unknown field" in p for p in problems)
    assert all("SECRET-SENTINEL" not in p and "api_key" not in p for p in problems)


@pytest.mark.parametrize("name", ["api_key", "API_SECRET", "binance_token", "password"])
def test_a_parameter_named_like_a_secret_is_rejected(name: str) -> None:
    problems = _problems(_plan(_bot(params={"lower": "1", name: "x"})))

    assert any("params" in p and "secret" in p.lower() for p in problems), problems
    assert all(name not in p for p in problems), (
        "the refusal repeated the parameter's name"
    )


def test_every_problem_is_listed_with_where_it_is() -> None:
    problems = _problems(
        _plan(
            _bot(kind="martingale"),
            _bot(name="second", venue="moon_testnet"),
            _bot(name="third", desired_state="paused"),
        )
    )

    joined = "\n".join(problems)
    assert "bots[0].kind" in joined and "grid" in joined, (
        "what was expected, not what was given"
    )
    assert "bots[1].venue" in joined and "spot_testnet" in joined
    assert "bots[2].desired_state" in joined


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ("not json at all", "not valid JSON"),
        ("[]", "JSON object"),
        (json.dumps({"bots": []}), "schema"),
        (json.dumps({"schema": "sew.bot-plan/2", "bots": []}), "sew.bot-plan/1"),
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


def test_two_entries_with_one_name_and_venue_are_refused_by_position_but_one_name_on_two_venues_is_fine() -> (
    None
):
    problems = _problems(_plan(_bot(), _bot(symbol="ETHUSDT")))

    assert any("bots[1]" in p and "bots[0]" in p for p in problems), problems

    document = parse_plan(_plan(_bot(), _bot(venue="spot_mainnet")), CATALOG)
    assert len(document.bots) == 2


def test_a_new_kind_in_the_catalog_needs_no_change_in_the_plan_code() -> None:
    catalog = BotKindCatalog([StubKind("grid"), StubKind("dca")])

    document = parse_plan(_plan(_bot(kind="dca")), catalog)

    assert document.bots[0].kind == "dca"


def test_the_numbers_stay_text_so_no_float_touches_a_price() -> None:
    with pytest.raises(InvalidBotPlanError) as raised:
        parse_plan(_plan(_bot(params={"lower": 60000.1})), CATALOG)

    assert any("parameter 1" in p and "text" in p for p in raised.value.problems)
    assert all("lower" not in p for p in raised.value.problems), "a name is not echoed"


_CANARY = "CANARY-6d2f81c4-never-echo-me"


@pytest.mark.parametrize(
    "plan",
    [
        json.dumps({"schema": _CANARY, "bots": []}),
        json.dumps({_CANARY: 1, "schema": SCHEMA, "bots": []}),
        _plan(_bot(kind=_CANARY)),
        _plan(_bot(venue=_CANARY)),
        _plan(_bot(desired_state=_CANARY)),
        _plan(_bot(**{_CANARY: "x"})),
        _plan(_bot(params={_CANARY: "x"})),
        _plan(_bot(params={"lower": 1, "api_key": _CANARY})),
        _plan(_bot(name=_CANARY), _bot(name=_CANARY)),
        _plan(_bot(name=3, symbol=_CANARY)),
    ],
    ids=[
        "schema value",
        "top-level field name",
        "kind value",
        "venue value",
        "desired_state value",
        "bot field name",
        "param name",
        "param value of a secret-like param",
        "duplicate name",
        "wrong-typed name beside a symbol",
    ],
)
def test_no_message_repeats_a_value_or_a_field_name_the_file_supplied(
    plan: str,
) -> None:
    try:
        parse_plan(plan, CATALOG)
    except InvalidBotPlanError as invalid:
        assert _CANARY not in str(invalid) and _CANARY not in "\n".join(
            invalid.problems
        )
    else:
        # a valid plan echoes nothing, by definition; only the duplicate-name case can be one
        pass
