"""`BUG-262` - an order session refused for the connection says which failure, not "check your key".

@details The owner's resume sent 44 s after a host start was refused with "check your API key/network
connection" although the key was fine and the same command passed 15 s later. The refusal now carries
the failure the connection check named and words it as the Connect step does.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connection_failure_words import (
    CONNECTION_FAILURE_SENTENCES,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_block_words import (
    SESSION_BLOCK_WORDS,
    refusal_words,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionBlockReason,
    SessionReadyResult,
)

_TRANSIENT = {
    ConnectionFailureKind.NETWORK,
    ConnectionFailureKind.MAINTENANCE,
    ConnectionFailureKind.RATE_LIMITED,
}


def _refused(kind: ConnectionFailureKind | None) -> SessionReadyResult:
    return SessionReadyResult(
        ready=False,
        block_reason=SessionBlockReason.CONNECTION_NOT_READY,
        reconciled_positions=(),
        reconciled_open_orders=(),
        connection_failure=kind,
    )


@pytest.mark.parametrize("kind", list(ConnectionFailureKind), ids=lambda k: k.value)
def test_each_failure_the_check_names_is_worded_by_its_own_sentence(
    kind: ConnectionFailureKind,
) -> None:
    words = refusal_words(_refused(kind))

    assert CONNECTION_FAILURE_SENTENCES[kind] in words
    assert words.startswith("Connection to the exchange is not ready: ")


def test_a_pause_is_not_called_a_key_problem_and_says_to_retry_soon() -> None:
    words = refusal_words(_refused(ConnectionFailureKind.RATE_LIMITED))

    assert "API key" not in words.replace("Nothing is wrong with the key", "")
    assert "try again in a few seconds" in words


@pytest.mark.parametrize("kind", list(ConnectionFailureKind), ids=lambda k: k.value)
def test_only_a_failure_that_can_clear_by_itself_says_to_retry(
    kind: ConnectionFailureKind,
) -> None:
    assert ("try again in a few seconds" in refusal_words(_refused(kind))) is (
        kind in _TRANSIENT
    )


def test_a_check_that_named_no_failure_keeps_the_general_sentence() -> None:
    assert (
        refusal_words(_refused(None))
        == SESSION_BLOCK_WORDS[SessionBlockReason.CONNECTION_NOT_READY]
    )
