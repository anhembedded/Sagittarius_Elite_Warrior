"""`BUG-262` - an order session refused for the connection says which failure, not "check your key".

@details The owner's resume sent 44 s after a host start was refused with "check your API key/network
connection" although the key was fine and the same command passed 15 s later. The refusal now carries
the failure the connection check named and words it as the Connect step does.
"""

from __future__ import annotations

from datetime import timedelta

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


def _refused(
    kind: ConnectionFailureKind | None,
    retry_after: timedelta | None = None,
    banned: bool = False,
) -> SessionReadyResult:
    return SessionReadyResult(
        ready=False,
        block_reason=SessionBlockReason.CONNECTION_NOT_READY,
        reconciled_positions=(),
        reconciled_open_orders=(),
        connection_failure=kind,
        connection_retry_after=retry_after,
        connection_banned=banned,
    )


@pytest.mark.parametrize("kind", list(ConnectionFailureKind), ids=lambda k: k.value)
def test_each_failure_the_check_names_is_worded_by_its_own_sentence(
    kind: ConnectionFailureKind,
) -> None:
    words = refusal_words(_refused(kind))

    assert CONNECTION_FAILURE_SENTENCES[kind] in words
    assert words.startswith("Connection to the exchange is not ready: ")


def test_a_pause_says_how_long_the_exchange_asked_for_and_not_a_few_seconds() -> None:
    words = refusal_words(
        _refused(ConnectionFailureKind.RATE_LIMITED, timedelta(seconds=12))
    )

    assert "asked for a pause of 12 s: try again after that." in words
    assert "few seconds" not in words


def test_a_ban_says_it_is_a_ban_and_how_long_so_no_one_retries_into_it() -> None:
    words = refusal_words(
        _refused(ConnectionFailureKind.RATE_LIMITED, timedelta(hours=2), banned=True)
    )

    assert "banned this address for 7200 s" in words
    assert "few seconds" not in words


def test_a_pause_whose_length_is_unknown_still_says_to_wait_for_it() -> None:
    assert "Wait for the pause to end" in refusal_words(
        _refused(ConnectionFailureKind.RATE_LIMITED)
    )


def test_only_a_network_failure_says_to_retry_in_a_few_seconds() -> None:
    said_it = {
        kind
        for kind in ConnectionFailureKind
        if "few seconds" in refusal_words(_refused(kind, timedelta(seconds=5)))
    }

    assert said_it == {ConnectionFailureKind.NETWORK}


def test_a_check_that_named_no_failure_keeps_the_general_sentence() -> None:
    assert (
        refusal_words(_refused(None))
        == SESSION_BLOCK_WORDS[SessionBlockReason.CONNECTION_NOT_READY]
    )
