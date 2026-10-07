"""`BUG-175` — `save_mainnet_key.py` says why a key was refused and what to do.

@details Over the real enrolment seam with a refusing gate: nothing is stored,
the exit status is 1, and the owner reads the exchange's own code and message,
the reason and the usual fixes (the run that printed only
"Nothing stored: KEY_REJECTED").
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.scripts import save_mainnet_key
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)


def test_a_refused_key_prints_the_exchanges_words_and_stores_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    reply = (
        "-2015 Invalid API-key, IP, or permissions for action. The key's IP whitelist"
    )
    monkeypatch.setattr(save_mainnet_key, "getpass", lambda _prompt: "a-key")
    monkeypatch.setattr(
        save_mainnet_key,
        "enrol_key",
        lambda *_args: ConnectFailure(
            AccountSource.SPOT_MAINNET, ConnectionFailureKind.KEY_REJECTED, "", reply
        ),
    )

    status = save_mainnet_key.main(["save_mainnet_key.py", "spot"])

    printed = capsys.readouterr().out
    assert status == 1
    assert "Nothing stored: KEY_REJECTED" in printed
    assert f"The exchange said: {reply}" in printed
