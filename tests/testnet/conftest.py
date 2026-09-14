"""`EPIC-021J` §2.3 — `tests/testnet/` is the one tier that touches the real
Binance Futures Testnet. Two independent gates, both required, because one
was already proven not enough: a tier gated only by a conditional skip runs
for real the moment someone happens to have that environment variable set
in their shell.

**Gate 1 — `ci-local.ps1`** never invokes this directory in any mode,
including `-Full`; only its own `-TestnetOnly` switch does.

**Gate 2 — this fixture** — `SEW_TESTNET_TESTS=1` *and* resolvable Futures
Testnet credentials, checked separately so a missing-one-vs-the-other run
skips with a reason that actually says which is missing.
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
from sagittarius_engine.utils.path_utils import PathUtils

#: The switch a person must set explicitly — never true by accident the way
#: a stray environment variable from an unrelated project could be.
ENV_FLAG = "SEW_TESTNET_TESTS"


@pytest.fixture(scope="session")
def testnet_credentials() -> ExchangeCredentials:
    """@brief Real Futures Testnet API credentials, or a `pytest.skip` with
    a reason naming exactly which of the two gates is closed."""
    if os.environ.get(ENV_FLAG) != "1":
        pytest.skip(f"missing {ENV_FLAG}=1 — this tier does not run in regular CI")

    secrets_file_path = PathUtils.get_relative_path(
        __file__, "..", "..", "src", "config", "secrets.local.json"
    )
    resolution = EnvFirstCredentialsProvider(
        SecretsFileSource(secrets_file_path)
    ).resolve()
    if resolution.credentials is None:
        pytest.skip(
            f"{ENV_FLAG}=1 is set but no Futures Testnet credentials were found"
        )
    return resolution.credentials
