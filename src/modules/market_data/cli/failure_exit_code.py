"""The exit code a failed market-data command deserves (`EPIC-038B`).

`sync` and `stream` classify a failure the same way; one function keeps the two
from drifting.
"""

from __future__ import annotations

from binance.exceptions import BinanceAPIException, BinanceRequestException
from pydantic import ValidationError
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode


def failure_exit_code(error: Exception) -> ExitCode:
    """A request the command rejects is `USAGE`, an exchange or network failure
    is `EXCHANGE`, anything else `ERROR`."""
    if isinstance(error, ValueError | ValidationError):
        return ExitCode.USAGE
    if isinstance(
        error, BinanceAPIException | BinanceRequestException | RequestException
    ):
        return ExitCode.EXCHANGE
    return ExitCode.ERROR
