import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.credentials.remove_key.command import (
    RemoveKeyCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_enrolment import (
    KeyRemoval,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_secret_store import (
    SecretStoreUnavailableError,
)

logger = logging.getLogger("App.KeyEnrolment")


class RemoveKeyCommandHandler(ICommandHandler[RemoveKeyCommand, KeyRemoval]):
    """@brief Handler for `RemoveKeyCommand` (`BUG-176`): asks the venue's own
    credentials provider to forget what it stored."""

    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(self, command: RemoveKeyCommand) -> KeyRemoval:
        provider = self._contexts.get(command.venue).credentials_provider
        source = provider.resolve().source
        if source is CredentialsSource.ENV:
            return KeyRemoval.FROM_ENVIRONMENT
        if source is CredentialsSource.NONE:
            return KeyRemoval.NOTHING_STORED
        try:
            provider.remove_stored()
        except SecretStoreUnavailableError as exc:
            logger.warning(
                "%s: the key could not be removed: %s [key-enrolment]",
                command.venue.display_name,
                exc,
            )
            return KeyRemoval.KEYRING_UNAVAILABLE
        except OSError as exc:
            logger.warning(
                "%s: the key could not be removed: %s [key-enrolment]",
                command.venue.display_name,
                exc,
            )
            return KeyRemoval.FILE_NOT_WRITABLE
        logger.info(
            "%s: the key was removed [key-enrolment]", command.venue.display_name
        )
        return KeyRemoval.REMOVED
