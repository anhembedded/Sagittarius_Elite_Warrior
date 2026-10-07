"""`BUG-176` — asks one environment whether it knows a key.

@details One read of the account per call, nothing placed or changed. Never
raises: every way the exchange can answer is a `KeyStanding`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    EnvironmentVerdict,
    KeyEnvironment,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)


class IKeyEnvironmentProbe(ABC):
    @abstractmethod
    def probe(
        self, environment: KeyEnvironment, credentials: ExchangeCredentials
    ) -> EnvironmentVerdict:
        """What `environment` says of `credentials`."""
