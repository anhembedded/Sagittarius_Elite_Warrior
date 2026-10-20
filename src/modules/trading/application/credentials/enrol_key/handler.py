import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.credentials.classify_key import (
    classify_key,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.credentials.enrol_key.command import (
    EnrolKeyCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_environment_probe import (
    IKeyEnvironmentProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_check import (
    KeyCheckRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_enrolment import (
    EnrolmentRefusal,
    KeyEnrolment,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    EnvironmentVerdict,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.KeyEnrolment")

#: What `classify_key` refuses, in the words the enrolment's callers already read.
_ENROLMENT_REFUSALS = {
    KeyCheckRefusal.INCOMPLETE: EnrolmentRefusal.INCOMPLETE,
    KeyCheckRefusal.NOT_A_KEY: EnrolmentRefusal.NOT_A_KEY,
    KeyCheckRefusal.NOT_ACCEPTED: EnrolmentRefusal.NOT_ACCEPTED,
    KeyCheckRefusal.WITHDRAWAL_ENABLED: EnrolmentRefusal.WITHDRAWAL_ENABLED,
    KeyCheckRefusal.NO_TRADING_PERMISSION: EnrolmentRefusal.NO_TRADING_PERMISSION,
}


class EnrolKeyCommandHandler(ICommandHandler[EnrolKeyCommand, KeyEnrolment]):
    """@brief Handler for `EnrolKeyCommand` (`BUG-176`), the one path that keeps a
    Binance key: the Options page's Add key and Replace, nothing else.

    @details Asks each environment in turn and stops at the first that accepts the
    key (a key is valid in exactly one). Then:

    - a mainnet key that can withdraw is refused (`EPIC-034` D5); one that cannot is
      kept in the keyring for Spot Mainnet if it may trade Spot and for Futures
      Mainnet if it may trade Futures;
    - a testnet key is kept for the testnet venue that accepted it, under that
      venue's own entry of `secrets.local.json`;
    - nothing is kept when no environment accepts the key, and a venue whose key
      is an environment variable is never written (the variable would win).

    Storing goes through each venue's own credentials provider, so a venue's key
    lives where `VenueAssembly` reads it from, and another venue's is never touched.
    """

    def __init__(self, probe: IKeyEnvironmentProbe, contexts: IVenueContexts) -> None:
        self._probe = probe
        self._contexts = contexts

    def execute(self, command: EnrolKeyCommand) -> KeyEnrolment:
        checked = classify_key(self._probe, command.credentials)
        if checked.refusal is not None:
            return KeyEnrolment(
                (), checked.verdicts, _ENROLMENT_REFUSALS[checked.refusal]
            )
        verdicts = checked.verdicts
        venues = checked.venues
        if command.only_for is not None:
            if command.only_for not in venues:
                return KeyEnrolment((), verdicts, EnrolmentRefusal.OTHER_VENUE, venues)
            venues = (command.only_for,)
        return self._store(command.credentials, venues, verdicts)

    def _store(
        self,
        credentials: ExchangeCredentials,
        venues: tuple[TradingVenue, ...],
        verdicts: tuple[EnvironmentVerdict, ...],
    ) -> KeyEnrolment:
        providers = {v: self._contexts.get(v).credentials_provider for v in venues}
        from_environment = tuple(
            v
            for v, p in providers.items()
            if p.resolve().source.is_provisioned_outside_the_app
        )
        if from_environment:
            return KeyEnrolment(
                (), verdicts, EnrolmentRefusal.FROM_ENVIRONMENT, from_environment
            )
        stored: list[TradingVenue] = []
        for venue, provider in providers.items():
            try:
                provider.save_to_file(credentials.api_key, credentials.api_secret)
            except SecretStoreUnavailableError as exc:
                logger.warning(
                    "%s: the key could not be kept: %s [key-enrolment]",
                    venue.display_name,
                    exc,
                )
                return KeyEnrolment(
                    tuple(stored), verdicts, EnrolmentRefusal.KEYRING_UNAVAILABLE
                )
            except OSError as exc:
                logger.warning(
                    "%s: the key could not be written: %s [key-enrolment]",
                    venue.display_name,
                    exc,
                )
                return KeyEnrolment(
                    tuple(stored), verdicts, EnrolmentRefusal.FILE_NOT_WRITABLE
                )
            stored.append(venue)
            logger.info(
                "%s: the key was kept [key-enrolment]",
                venue.display_name,
            )
        return KeyEnrolment(tuple(stored), verdicts)
