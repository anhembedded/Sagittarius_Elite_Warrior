"""`EPIC-045B` - `bot delete` on the running host runs the screen's own Delete for one bot at rest.

The chain is the real one (`add_delete_host_world.py`): the host handler, the screen's delete and the
Grid kind reading a record the real runtime codec wrote. What is proven: only a DRAFT or STOPPED bot
is deleted; a record that still shows a held base, a live order, an owed order or an open protective
stop keeps the bot; nothing is sent to the exchange; the command lock is held.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot import (
    DeleteBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedBot,
    AppliedPlan,
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import JsonValue
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
    HeldOrder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.add_delete_host_world import (
    a_host,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.edit_host_world import (
    AT_REST,
    NOT_AT_REST,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.grid_runtime_builders import (
    started_ladder,
)

S = BotLifecycleState


def _flat() -> GridRuntime:
    """A stopped ladder: no level holds an order, no base, nothing owed."""
    return GridRuntime(levels=())


def _record(runtime: GridRuntime) -> dict[str, JsonValue]:
    return encode_runtime(runtime)


@pytest.mark.parametrize("state", AT_REST)
def test_a_bot_at_rest_that_holds_nothing_is_deleted_by_the_screens_own_delete(
    state: BotLifecycleState,
) -> None:
    host = a_host()
    host.hold(state, _record(_flat()))

    result = host.delete()

    assert result.accepted, result.message
    assert host.ids == []
    assert host.dispatcher.dispatched == [DeleteBotCommand(BOT)]
    assert "nothing was sent to the exchange" in result.message


def test_a_deleted_bots_wish_goes_with_it_and_another_bots_wish_stays() -> None:
    """`EPIC-045C`: a row for a bot that no longer exists acts on nothing, so the delete removes it."""
    host = a_host()
    host.hold(S.STOPPED, _record(_flat()))
    host.plans.write(
        AppliedPlan(
            (
                AppliedBot(BOT, "grid one", "spot_testnet", DesiredState.RUNNING),
                AppliedBot("other1", "kept", "spot_testnet", DesiredState.RUNNING),
            )
        )
    )

    assert host.delete().accepted

    record = host.plans.read()
    assert record is not None and [row.bot_id for row in record.bots] == ["other1"]


def test_a_refused_delete_keeps_the_bots_wish() -> None:
    host = a_host()
    host.hold(S.RUNNING, _record(_flat()))
    host.plans.write(
        AppliedPlan(
            (AppliedBot(BOT, "grid one", "spot_testnet", DesiredState.RUNNING),)
        )
    )

    assert not host.delete().accepted

    record = host.plans.read()
    assert record is not None and record.desired_for(BOT) is DesiredState.RUNNING


def test_a_draft_that_never_ran_has_an_empty_record_and_is_deleted() -> None:
    host = a_host()
    host.hold(S.DRAFT)

    assert host.delete().accepted
    assert host.ids == []


@pytest.mark.parametrize("state", NOT_AT_REST, ids=lambda s: s.value)
def test_every_other_state_is_refused_in_words_and_the_bot_stays(
    state: BotLifecycleState,
) -> None:
    host = a_host()
    host.hold(state, _record(_flat()))

    result = host.delete()

    assert not result.accepted
    assert result.refusal is BotRefusal.INVALID_TRANSITION
    assert f"is {state.value}" in result.message
    assert "only a DRAFT or STOPPED bot can be deleted" in result.message
    assert "Nothing was deleted" in result.message
    assert host.ids == [BOT]
    assert host.dispatcher.dispatched == []


def test_an_unknown_id_is_refused_as_the_screen_refuses_it() -> None:
    host = a_host()

    result = host.delete("zzzzzz")

    assert not result.accepted
    assert result.refusal is BotRefusal.NOT_FOUND


@pytest.mark.parametrize(
    ("runtime", "words"),
    [
        (replace(_flat(), inventory=Decimal("0.5")), "0.5 of the base"),
        (replace(_flat(), earlier_runs_base=Decimal("0.5")), "0.5 of the base"),
        (
            replace(
                _flat(),
                inventory=Decimal("0.0002"),
                mark_price=Decimal(50000),
            ),
            "0.0002 of the base",
        ),
        (started_ladder(), "resting at its levels"),
        (
            replace(_flat(), held=(HeldOrder(0, OrderSide.BUY, Decimal(1)),)),
            "owes a level",
        ),
    ],
    ids=["inventory", "earlier-runs-base", "worth-ten", "live-order", "owed-order"],
)
def test_a_record_that_still_shows_exposure_keeps_the_bot(
    runtime: GridRuntime, words: str
) -> None:
    host = a_host()
    host.hold(S.STOPPED, _record(runtime))

    result = host.delete()

    assert not result.accepted
    assert result.refusal is BotRefusal.EXPOSURE_LEFT
    assert words in result.message
    assert "Nothing was deleted" in result.message
    assert host.ids == [BOT]
    assert host.dispatcher.dispatched == []


def test_an_unreadable_record_keeps_the_bot() -> None:
    host = a_host()
    host.hold(S.STOPPED, {"inventory": "lots"})

    result = host.delete()

    assert result.refusal is BotRefusal.EXPOSURE_LEFT
    assert "not known" in result.message
    assert host.ids == [BOT]


def test_an_open_protective_stop_keeps_the_bot_and_an_ended_one_does_not() -> None:
    host = a_host()
    stop = {"client_order_id": "c", "side": "SELL", "trigger_price": "1"}
    host.hold(
        S.STOPPED,
        {**_record(_flat()), "protective_stops": [{**stop, "state": "standing"}]},
    )
    assert host.delete().refusal is BotRefusal.EXPOSURE_LEFT

    host.hold(
        S.STOPPED,
        {**_record(_flat()), "protective_stops": [{**stop, "state": "ended"}]},
    )
    assert host.delete().accepted


def test_the_delete_runs_under_the_command_lock() -> None:
    host = a_host()
    host.hold(S.DRAFT)
    seen: list[bool] = []
    inner = host.dispatcher.handlers[DeleteBotCommand]
    original = inner.execute

    def watching(command: DeleteBotCommand):  # type: ignore[no-untyped-def]
        seen.append(host.lock.is_held)
        return original(command)

    inner.execute = watching  # type: ignore[method-assign]

    host.delete()

    assert seen == [True]
    assert not host.lock.is_held


def test_a_remainder_worth_less_than_ten_quote_units_is_dust_and_does_not_keep_the_bot() -> (
    None
):
    host = a_host()
    dust = replace(
        _flat(), inventory=Decimal("0.000199"), mark_price=Decimal(50000)
    )  # 9.95
    host.hold(S.STOPPED, _record(dust))

    assert host.delete().accepted


def test_a_remainder_is_valued_at_the_highest_price_the_record_holds() -> None:
    host = a_host()
    # 0.0002 is worth 10 at 50000 (kept) although the last mark, 10000, would call it dust.
    record = _record(
        replace(
            started_ladder(),
            inventory=Decimal("0.0002"),
            mark_price=Decimal(10000),
            start_price=Decimal(50000),
        )
    )
    record["levels"] = []
    host.hold(S.STOPPED, record)

    assert host.delete().refusal is BotRefusal.EXPOSURE_LEFT


def test_a_remainder_with_no_price_to_value_it_by_is_never_let_go() -> None:
    host = a_host()
    host.hold(S.STOPPED, _record(replace(_flat(), inventory=Decimal("0.000001"))))

    result = host.delete()

    assert result.refusal is BotRefusal.EXPOSURE_LEFT


def test_on_a_quote_that_is_not_a_dollar_every_nonzero_base_keeps_the_bot() -> None:
    """0.5 ETH at 0.035 BTC is 0.0175 of the quote: under 10, and worth about a thousand dollars."""
    host = a_host()
    holding = replace(_flat(), inventory=Decimal("0.5"), mark_price=Decimal("0.035"))
    host.hold(S.STOPPED, _record(holding), symbol="ETHBTC")

    result = host.delete()

    assert result.refusal is BotRefusal.EXPOSURE_LEFT
    assert host.ids == [BOT]


@pytest.mark.parametrize("symbol", ["BTCUSDT", "BTCUSDC", "BTCFDUSD"])
def test_a_dust_remainder_is_let_go_on_every_usd_stable_quote(symbol: str) -> None:
    host = a_host()
    dust = replace(_flat(), inventory=Decimal("0.000006"), mark_price=Decimal(50000))
    host.hold(S.STOPPED, _record(dust), symbol=symbol)

    assert host.delete().accepted


def test_a_short_and_an_earlier_long_do_not_cancel_each_other_out() -> None:
    host = a_host()
    opposed = replace(
        _flat(),
        inventory=Decimal(-1),
        earlier_runs_base=Decimal(1),
        mark_price=Decimal(50000),
    )
    host.hold(S.STOPPED, _record(opposed))

    assert host.delete().refusal is BotRefusal.EXPOSURE_LEFT
