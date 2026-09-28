"""`EPIC-027P` — `tests/testnet/spot/` is the one tier that touches the real
Binance Spot Testnet, mirroring `tests/testnet/conftest.py`'s own two-gate
structure exactly, with Spot's own credentials (ADR D8 — kept separate from
Futures Testnet's).

**Gate 1 — `ci-local.ps1`** never invokes `tests/testnet/` in any mode,
including `-Full`; only its own `-TestnetOnly` switch does (this
subdirectory needs no change there — `-TestnetOnly` already targets the
whole `tests/testnet` tree, and `-Full`'s `--ignore` already excludes it).

**Gate 2 — this fixture** — `SEW_TESTNET_TESTS=1` *and* resolvable Spot
Testnet credentials (`BINANCE_SPOT_TESTNET_API_KEY`/`_SECRET`, via
`EnvFirstCredentialsProvider`'s existing per-venue lookup, `EPIC-027G`),
checked separately so a missing-one-vs-the-other run skips with a reason
that actually says which is missing.
"""

from __future__ import annotations

import os

import pytest
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    EnvFirstCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.utils.path_utils import PathUtils

#: Same switch the Futures tier uses — one flag covers both, since either
#: tier touching a real exchange must be opted into deliberately.
ENV_FLAG = "SEW_TESTNET_TESTS"


@pytest.fixture(scope="session")
def spot_testnet_credentials() -> ExchangeCredentials:
    """@brief Real Spot Testnet API credentials, or a `pytest.skip` with a
    reason naming exactly which of the two gates is closed."""
    if os.environ.get(ENV_FLAG) != "1":
        pytest.skip(f"missing {ENV_FLAG}=1 — this tier does not run in regular CI")

    secrets_file_path = PathUtils.get_relative_path(
        __file__, "..", "..", "..", "src", "config", "secrets.local.json"
    )
    resolution = EnvFirstCredentialsProvider(
        SecretsFileSource(secrets_file_path), TradingVenue.SPOT_TESTNET
    ).resolve()
    if resolution.credentials is None:
        pytest.skip(f"{ENV_FLAG}=1 is set but no Spot Testnet credentials were found")
    return resolution.credentials
