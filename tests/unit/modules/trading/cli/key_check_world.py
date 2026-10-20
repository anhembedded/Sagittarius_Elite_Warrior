"""`BOT-200` — `key check` over the real use case, with no exchange.

@details `CheckKeyQueryHandler`, the report and the printer are the real ones; only the
exchange is scripted. The key and the secret are obvious sentinels: every test greps
what the command printed and logged for them.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.check_key import (
    CheckKeyQuery,
    CheckKeyQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_environment_probe import (
    IKeyEnvironmentProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    EnvironmentVerdict,
    KeyEnvironment,
    KeyStanding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_permissions import (
    KeyPermissions,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)

#: Obviously fake, alphanumeric like a real one, and easy to grep for.
SENTINEL_KEY = "SENTINELKEY" + "0" * 53
SENTINEL_SECRET = "SENTINELSECRET" + "0" * 50
SENTINELS = ("SENTINELKEY", "SENTINELSECRET")

#: What a real exchange says in the words of `describe_failure`; here a fixed sentence.
REFUSED_REASON = "-2015 Invalid API-key, IP, or permissions for action."
UNKNOWN_REASON = "-2008 Invalid Api-Key ID."


class ScriptedProbe(IKeyEnvironmentProbe):
    """Answers what each environment is told to say; records who was asked, in order."""

    def __init__(self, answers: dict[KeyEnvironment, EnvironmentVerdict]) -> None:
        self._answers = answers
        self.asked: list[KeyEnvironment] = []

    def probe(
        self, environment: KeyEnvironment, credentials: ExchangeCredentials
    ) -> EnvironmentVerdict:
        self.asked.append(environment)
        return self._answers.get(
            environment, EnvironmentVerdict(environment, KeyStanding.UNKNOWN)
        )


class HandlerDispatcher(ICommandDispatcher):
    """The dispatcher over the one query `key check` sends, answered by the real handler."""

    def __init__(self, probe: IKeyEnvironmentProbe) -> None:
        self._handler = CheckKeyQueryHandler(probe)

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        assert handler_class is CheckKeyQuery
        assert isinstance(input_dto, CheckKeyQuery)
        return self._handler.execute(input_dto)


def accepted(environment: KeyEnvironment) -> EnvironmentVerdict:
    return EnvironmentVerdict(environment, KeyStanding.ACCEPTED)


def mainnet_accepts(
    *, spot: bool = False, futures: bool = False, withdraw: bool = False
) -> EnvironmentVerdict:
    return EnvironmentVerdict(
        KeyEnvironment.MAINNET,
        KeyStanding.ACCEPTED,
        permissions=KeyPermissions(
            can_read=True,
            can_trade_spot=spot,
            can_withdraw=withdraw,
            can_trade_futures=futures,
        ),
    )


def unknown(environment: KeyEnvironment) -> EnvironmentVerdict:
    return EnvironmentVerdict(environment, KeyStanding.UNKNOWN, reason=UNKNOWN_REASON)


def refused(environment: KeyEnvironment) -> EnvironmentVerdict:
    return EnvironmentVerdict(environment, KeyStanding.REFUSED, reason=REFUSED_REASON)


def unreachable(environment: KeyEnvironment) -> EnvironmentVerdict:
    return EnvironmentVerdict(
        environment, KeyStanding.UNREACHABLE, failure=ConnectionFailureKind.NETWORK
    )


def sentinel_credentials() -> ExchangeCredentials:
    return ExchangeCredentials(SENTINEL_KEY, SENTINEL_SECRET)
