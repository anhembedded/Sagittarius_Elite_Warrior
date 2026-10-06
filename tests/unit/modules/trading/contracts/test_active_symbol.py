"""`BOT-149` — a pair active for several reasons is named once, by the
strongest, which is what ranks it on a capped page."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.active_symbol import (
    ActiveReason,
    ActiveSymbol,
    active_symbols_from,
)


def test_a_pair_with_several_reasons_is_named_once_by_the_strongest() -> None:
    active = active_symbols_from(
        [
            (ActiveReason.HELD, ["BBBUSDT", "CCCUSDT"]),
            (ActiveReason.TRADED, ["AAAUSDT", "BBBUSDT"]),
            (ActiveReason.OPEN_ORDER, ["BBBUSDT"]),
        ]
    )

    assert active == (
        ActiveSymbol("AAAUSDT", ActiveReason.TRADED),
        ActiveSymbol("BBBUSDT", ActiveReason.OPEN_ORDER),
        ActiveSymbol("CCCUSDT", ActiveReason.HELD),
    )


def test_the_strongest_reason_wins_whatever_order_the_reasons_arrive_in() -> None:
    forward = active_symbols_from(
        [(ActiveReason.OPEN_ORDER, ["AUSDT"]), (ActiveReason.HELD, ["AUSDT"])]
    )
    backward = active_symbols_from(
        [(ActiveReason.HELD, ["AUSDT"]), (ActiveReason.OPEN_ORDER, ["AUSDT"])]
    )

    assert forward == backward == (ActiveSymbol("AUSDT", ActiveReason.OPEN_ORDER),)
