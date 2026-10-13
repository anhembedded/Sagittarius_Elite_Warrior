"""`EPIC-039E` — the Futures settings gate: ensure, read back, compare (decisions D3, O5).

@details Business promise: a Futures bot's first order goes out only on a symbol whose margin
type and leverage are the ones its parameters name, on a One-way account; the gate changes only
what differs, says in words why it cannot when the symbol is busy, and never touches the
account's position mode. The REST pages for the two changes were not readable
(`EPIC-039E` notes), so the refusals the gate names are the error-code page's: `-4047`,
`-4048`, `-4161`.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue_settings_gate_futures import (
    FuturesSettingsGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.margin_mode import MarginMode
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_settings_gate_result import (
    GateOutcome,
    GateRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_rejected_error import (
    AccountControlRejectedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_result import (
    AccountControlRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.futures_world import (
    FUTURES,
    SYMBOL,
    FuturesWorld,
    a_futures_status,
)


def _ask(leverage: int = 3, mode: MarginMode = MarginMode.ISOLATED) -> GateRequest:
    return GateRequest(FUTURES, SYMBOL, leverage, mode)


def _gate(world: FuturesWorld) -> FuturesSettingsGate:
    return FuturesSettingsGate(world.ports)


def test_the_gate_sets_margin_type_then_leverage_and_reads_back() -> None:
    world = FuturesWorld(leverage=5, margin_type=MarginType.CROSSED)

    result = _gate(world).ensure(_ask(leverage=3))

    assert result.ensured
    assert world.settings.calls == ["change_margin_type", "change_leverage"]
    assert world.settings.margin_changes == [(SYMBOL, MarginType.ISOLATED)]
    assert world.settings.leverage_changes == [(SYMBOL, 3)]
    assert world.terms.setting == FuturesSymbolSetting(
        SYMBOL, 3, MarginType.ISOLATED, world.terms.setting.max_notional
    )


def test_it_writes_only_what_differs() -> None:
    world = FuturesWorld(leverage=3, margin_type=MarginType.CROSSED)

    assert _gate(world).ensure(_ask(leverage=3)).ensured
    assert world.settings.calls == ["change_margin_type"]

    already = FuturesWorld(leverage=3, margin_type=MarginType.ISOLATED)
    assert _gate(already).ensure(_ask(leverage=3)).ensured
    assert already.settings.calls == []


def test_a_settings_that_already_match_pass_even_with_the_ladder_resting() -> None:
    """A resume: the bot's own orders rest, nothing differs, so nothing is asked of the
    exchange and the symbol need not be flat."""
    world = FuturesWorld(leverage=3, margin_type=MarginType.ISOLATED)
    world.rests_an_order()
    world.holds_a_position("0.02")

    assert _gate(world).ensure(_ask(leverage=3)).ensured
    assert world.settings.calls == []


def test_a_mismatch_after_readback_is_a_start_refusal_naming_both_values() -> None:
    world = FuturesWorld(leverage=5, margin_type=MarginType.ISOLATED)
    world.settings.silently_ignores_changes = True

    result = _gate(world).ensure(_ask(leverage=3))

    assert result.outcome is GateOutcome.SETTINGS_MISMATCH
    assert "leverage 3 asked, exchange says 5" in result.detail


def test_a_mismatch_names_the_margin_type_too() -> None:
    world = FuturesWorld(leverage=3, margin_type=MarginType.CROSSED)
    world.settings.silently_ignores_changes = True

    result = _gate(world).ensure(_ask(leverage=3))

    assert result.outcome is GateOutcome.SETTINGS_MISMATCH
    assert "margin type isolated asked, exchange says crossed" in result.detail


@pytest.mark.parametrize("what", ["an order", "a position"])
def test_the_gate_refuses_with_an_open_order_or_position_on_the_symbol_in_words(
    what: str,
) -> None:
    world = FuturesWorld(leverage=5, margin_type=MarginType.CROSSED)
    if what == "an order":
        world.rests_an_order()
    else:
        world.holds_a_position("-0.02")

    result = _gate(world).ensure(_ask(leverage=3))

    assert result.outcome is GateOutcome.SYMBOL_NOT_FLAT
    assert SYMBOL in result.detail
    assert "Nothing was changed" in result.detail
    assert "-4" not in result.detail  # words, not a raw exchange code
    assert world.settings.calls == []


def test_an_order_on_another_symbol_does_not_block_the_change() -> None:
    world = FuturesWorld(leverage=5, margin_type=MarginType.ISOLATED)
    world.rests_an_order()
    (order,) = world.activity.open_orders()
    world.activity.holding_open_orders([replace(order, symbol="ETHUSDT")])

    assert _gate(world).ensure(_ask(leverage=3)).ensured


def _on(symbol: str, order):  # type: ignore[no-untyped-def]
    return replace(order, symbol=symbol)


def test_the_exchanges_own_refusal_is_carried_in_words() -> None:
    world = FuturesWorld(leverage=5, margin_type=MarginType.ISOLATED)
    world.settings.refuses_with(AccountControlRefusal.EXCHANGE_REJECTED, "-4161: nope")

    result = _gate(world).ensure(_ask(leverage=3))

    assert result.outcome is GateOutcome.EXCHANGE_REFUSED
    assert "-4161: nope" in result.detail


def test_hedge_mode_blocks_start() -> None:
    world = FuturesWorld(status=a_futures_status(PositionMode.HEDGE))

    result = _gate(world).ensure(_ask())

    assert result.outcome is GateOutcome.HEDGE_MODE_UNSUPPORTED
    assert "Hedge Mode" in result.detail
    assert world.settings.calls == []


def test_the_connection_checks_hedge_failure_blocks_start_too() -> None:
    world = FuturesWorld()
    world.account.answer_with(
        replace(
            a_futures_status(),
            failure=ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED,
            reachable=False,
        )
    )

    assert _gate(world).ensure(_ask()).outcome is GateOutcome.HEDGE_MODE_UNSUPPORTED


def test_an_unreachable_venue_is_unreadable_never_a_match() -> None:
    world = FuturesWorld()
    world.account.answer_with(
        replace(
            a_futures_status(), reachable=False, failure=ConnectionFailureKind.NETWORK
        )
    )

    assert _gate(world).ensure(_ask()).outcome is GateOutcome.SETTINGS_UNREADABLE


def test_the_gate_never_calls_a_position_mode_setter() -> None:
    """Position mode is account-wide: the control port has no setter for it, and the gate
    only ever calls the two it has."""
    world = FuturesWorld(leverage=5, margin_type=MarginType.CROSSED)

    _gate(world).ensure(_ask(leverage=3))
    _gate(world).verify(_ask(leverage=3))

    assert set(world.settings.calls) <= {"change_leverage", "change_margin_type"}
    assert not [name for name in dir(world.settings) if "position_mode" in name]


def test_verify_changes_nothing_and_names_a_drift() -> None:
    world = FuturesWorld(leverage=3, margin_type=MarginType.ISOLATED)
    assert _gate(world).verify(_ask(leverage=3)).ensured

    world.settings.move(leverage=7)
    result = _gate(world).verify(_ask(leverage=3))

    assert result.outcome is GateOutcome.SETTINGS_MISMATCH
    assert "leverage 3 asked, exchange says 7" in result.detail
    assert world.settings.calls == []


def test_a_change_the_gate_made_is_logged_at_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = FuturesWorld(leverage=5, margin_type=MarginType.ISOLATED)

    with caplog.at_level("INFO", logger="App.Bots.FuturesGate"):
        _gate(world).ensure(_ask(leverage=3))

    (record,) = caplog.records
    assert "[futures-gate]" in record.getMessage()
    assert SYMBOL in record.getMessage()
    assert "from 5 to 3" in record.getMessage()


@pytest.mark.parametrize("read", ["orders", "positions"])
def test_a_failed_read_of_the_symbols_orders_or_position_is_unreadable_not_a_raise(
    read: str,
) -> None:
    """Red before: the read ran outside any handler and a `ConnectionError` escaped `ensure`.
    A symbol whose orders or position could not be read is not known to be flat."""
    world = FuturesWorld(leverage=5, margin_type=MarginType.ISOLATED)
    if read == "orders":
        world.activity.open_orders_raise(ConnectionError("reset"))
    else:
        world.account.positions_raise(ConnectionError("reset"))

    result = _gate(world).ensure(_ask(leverage=3))

    assert result.outcome is GateOutcome.SETTINGS_UNREADABLE
    assert "reset" in result.detail
    assert world.settings.calls == []


def test_a_refused_leverage_says_the_margin_type_was_already_changed() -> None:
    """Red before: the user read only the leverage refusal while the exchange already held
    the new margin type."""
    world = FuturesWorld(leverage=5, margin_type=MarginType.CROSSED)
    world.settings.leverage_error = AccountControlRejectedError(
        -4028, "Leverage 3 is not valid"
    )

    result = _gate(world).ensure(_ask(leverage=3))

    assert result.outcome is GateOutcome.EXCHANGE_REFUSED
    assert "-4028" in result.detail
    assert "margin type was already changed to isolated" in result.detail
    assert "leverage 3 asked, exchange says 5" in result.detail
