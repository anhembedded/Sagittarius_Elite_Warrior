import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.credentials.enrol_key.command import (
    EnrolKeyCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_environment_probe import (
    IKeyEnvironmentProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_enrolment import (
    EnrolmentRefusal,
    KeyEnrolment,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    EnvironmentVerdict,
    KeyEnvironment,
    KeyStanding,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_secret_store import (
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.KeyEnrolment")

_TESTNET_VENUES = {
    KeyEnvironment.SPOT_TESTNET: TradingVenue.SPOT_TESTNET,
    KeyEnvironment.FUTURES_TESTNET: TradingVenue.FUTURES_TESTNET,
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
        credentials = command.credentials
        if not credentials.api_key.strip() or not credentials.api_secret.strip():
            return KeyEnrolment((), refusal=EnrolmentRefusal.INCOMPLETE)
        if not (credentials.api_key.isascii() and credentials.api_secret.isascii()):
            return KeyEnrolment((), refusal=EnrolmentRefusal.NOT_A_KEY)

        verdicts: list[EnvironmentVerdict] = []
        accepted: EnvironmentVerdict | None = None
        for environment in KeyEnvironment:
            verdict = self._probe.probe(environment, credentials)
            verdicts.append(verdict)
            if verdict.standing is KeyStanding.ACCEPTED:
                accepted = verdict
                break
        if accepted is None:
            return KeyEnrolment((), tuple(verdicts), EnrolmentRefusal.NOT_ACCEPTED)

        decided = self._venues_for(accepted)
        if isinstance(decided, EnrolmentRefusal):
            return KeyEnrolment((), tuple(verdicts), decided)
        venues = decided
        if command.only_for is not None:
            if command.only_for not in venues:
                return KeyEnrolment(
                    (), tuple(verdicts), EnrolmentRefusal.OTHER_VENUE, venues
                )
            venues = (command.only_for,)
        return self._store(credentials, venues, tuple(verdicts))

    @staticmethod
    def _venues_for(
        accepted: EnvironmentVerdict,
    ) -> tuple[TradingVenue, ...] | EnrolmentRefusal:
        if accepted.environment is not KeyEnvironment.MAINNET:
            return (_TESTNET_VENUES[accepted.environment],)
        permissions = accepted.permissions
        if permissions is None or permissions.can_withdraw:
            return EnrolmentRefusal.WITHDRAWAL_ENABLED
        venues = tuple(
            venue
            for venue, allowed in (
                (TradingVenue.SPOT_MAINNET, permissions.can_trade_spot),
                (TradingVenue.FUTURES_MAINNET, permissions.can_trade_futures),
            )
            if allowed
        )
        return venues or EnrolmentRefusal.NO_TRADING_PERMISSION

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
            if p.resolve().source is CredentialsSource.ENV
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
                "%s: the key %s was kept [key-enrolment]",
                venue.display_name,
                credentials,
            )
        return KeyEnrolment(tuple(stored), verdicts)
