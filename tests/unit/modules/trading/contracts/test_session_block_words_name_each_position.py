"""`BUG-250` - what a refused opening says of each position it would not excuse."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_block_words import (
    SESSION_BLOCK_WORDS,
    UNEXPLAINED_POSITION_WORDS,
    refusal_words,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionBlockReason,
    SessionReadyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.unexplained_position import (
    PositionUnexplainedWhy,
    UnexplainedPosition,
)


def _refused(*positions: UnexplainedPosition) -> SessionReadyResult:
    return SessionReadyResult(
        ready=False,
        block_reason=SessionBlockReason.UNEXPECTED_POSITIONS,
        reconciled_positions=(),
        reconciled_open_orders=(),
        unexplained_positions=positions,
    )


def test_every_reason_a_position_is_not_excused_has_its_words() -> None:
    assert set(UNEXPLAINED_POSITION_WORDS) == set(PositionUnexplainedWhy)


def test_a_refusal_with_no_position_detail_is_the_plain_sentence() -> None:
    plain = SESSION_BLOCK_WORDS[SessionBlockReason.UNEXPECTED_POSITIONS]

    assert refusal_words(_refused()) == plain


def test_each_position_is_named_with_the_figures_of_its_reason() -> None:
    words = refusal_words(
        _refused(
            UnexplainedPosition(
                "ETHUSDT", Decimal("0.300"), PositionUnexplainedWhy.NO_CLAIM
            ),
            UnexplainedPosition(
                "BNBUSDT",
                Decimal("1.5"),
                PositionUnexplainedWhy.DIFFERS_FROM_HISTORY,
                Decimal("1.2"),
            ),
            UnexplainedPosition(
                "BTCUSDT", Decimal("-0.01"), PositionUnexplainedWhy.HISTORY_UNVERIFIABLE
            ),
        )
    )

    assert "ETHUSDT holds 0.300 and no bot of this venue claims it" in words
    assert (
        "BNBUSDT holds 1.5 but the claiming bot's own orders account for 1.2" in words
    )
    assert "BTCUSDT holds -0.01 and the order history that would explain it" in words
    assert "; " in words
