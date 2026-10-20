from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.credentials.classify_key import (
    classify_key,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.check_key.query import (
    CheckKeyQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_environment_probe import (
    IKeyEnvironmentProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_check import (
    KeyCheck,
    KeyCheckRefusal,
)


def _is_a_binance_value(value: str) -> bool:
    """Printable ASCII with no space: a Binance key and secret are letters and digits,
    and a value with a space or a control character was mispasted."""
    return (
        value.isascii() and value.isprintable() and not any(c.isspace() for c in value)
    )


class CheckKeyQueryHandler(IQueryHandler[CheckKeyQuery, KeyCheck]):
    """@brief Asks each environment about a key and says which venues it is for,
    keeping nothing (`BOT-200`).

    @details The question `EnrolKeyCommandHandler` asks before it keeps a key
    (`classify_key`), for the command line: the server's keys are written by a
    root-run script, never by the app, so the app only checks. A value that is not
    printable ASCII without a space is refused before the exchange is asked: it
    would only be told as a network failure.
    """

    def __init__(self, probe: IKeyEnvironmentProbe) -> None:
        self._probe = probe

    def execute(self, query: CheckKeyQuery) -> KeyCheck:
        credentials = query.credentials
        both = (credentials.api_key, credentials.api_secret)
        if all(value.strip() for value in both) and not all(
            _is_a_binance_value(value) for value in both
        ):
            return KeyCheck((), refusal=KeyCheckRefusal.NOT_A_KEY)
        return classify_key(self._probe, credentials)
