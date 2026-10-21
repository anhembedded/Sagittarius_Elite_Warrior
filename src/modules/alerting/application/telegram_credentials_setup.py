"""Save, remove and describe the Telegram bot token and chat id the Options page manages
(`EPIC-036D4`).

The sibling of `DiscordWebhookSetup` for a channel with two values. The bot token is the
secret (N3): whoever holds it can post as the bot. So this class takes the pair in, validates
both against the shapes Telegram issues, hands them to the store and gives back no more than
an enum and a state that carries four characters of the token and the chat id (a chat is a
place, not a secret). No log line or exception text it makes holds the token.

What the app can write is the keyring (`OrderedSecretStores` marks one writable backend). On a
host that provisions the credentials elsewhere that value is read first, so a save would change
nothing the channel uses: the read-back after the writes catches it (`OVERRIDDEN`). Saving
over a stored pair is the rotation: the new pair replaces the old one, and nothing else.

The channel reads both secrets at each send, so a saved pair applies to the next send; the
Telegram lane starts only at boot, so `TelegramChannelState.running` says whether this run has it
(`Docs/MODULES/alerting/06-runtime.md`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    ISecretStore,
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel_catalog import (
    IAlertChannelCatalog,
)

logger = logging.getLogger("App.Alerting")

#: How many characters of the token the state shows, so the owner can tell two bots apart.
HINT_CHARS = 4


@dataclass(frozen=True, slots=True)
class TelegramChannelSpec:
    """What names the channel and its two secrets, and what a usable value looks like.
    Composition fills it from the adapter's constants, so this layer imports no adapter."""

    channel_id: str
    token_secret: str
    chat_secret: str
    is_bot_token: Callable[[str], bool]
    is_chat_id: Callable[[str], bool]
    #: What the app's own writable store holds under a name, ignoring the provisioned stores:
    #: what a failed save puts back, never a copy of a secret the operator keeps elsewhere.
    read_own: Callable[[str], str | None]


class TelegramSave(Enum):
    SAVED = "saved"
    EMPTY_TOKEN = "empty token"  # noqa: S105 - an outcome's name, not a secret
    EMPTY_CHAT = "empty chat"
    NOT_A_BOT_TOKEN = "not a bot token"  # noqa: S105 - an outcome's name, not a secret
    NOT_A_CHAT_ID = "not a chat id"
    STORE_UNAVAILABLE = "store unavailable"
    #: Written, but another store answers first on this host, so it is not the one in use.
    OVERRIDDEN = "overridden by another store"


class TelegramRemoval(Enum):
    REMOVED = "removed"
    NOTHING_STORED = "nothing stored"
    STORE_UNAVAILABLE = "store unavailable"
    #: The app's store forgot them, but another store still holds a value.
    STILL_SET_ELSEWHERE = "still set by another store"


@dataclass(frozen=True, slots=True)
class TelegramChannelState:
    #: Some store holds a value under either secret's name.
    stored: bool
    #: ... and both are of the shape Telegram issues.
    usable: bool
    #: The last characters of a usable token; "" otherwise. Never the token.
    hint: str
    #: The chat id of a usable pair; "" otherwise. A chat is not a secret.
    chat: str
    #: This run has the channel (it was configured when the app booted).
    running: bool


class TelegramCredentialsSetup:
    def __init__(
        self,
        secrets: ISecretStore,
        spec: TelegramChannelSpec,
        catalog: IAlertChannelCatalog,
    ) -> None:
        self._secrets = secrets
        self._spec = spec
        self._catalog = catalog

    def state(self) -> TelegramChannelState:
        token, chat = self._stored()
        usable = bool(token and chat) and (
            self._spec.is_bot_token(token) and self._spec.is_chat_id(chat)
        )
        return TelegramChannelState(
            stored=bool(token or chat),
            usable=usable,
            hint=token[-HINT_CHARS:] if usable else "",
            chat=chat if usable else "",
            running=self._spec.channel_id in self._catalog.channel_ids(),
        )

    def save(self, token: str, chat: str) -> TelegramSave:
        """Stores the pair when both are of the shape Telegram issues; otherwise stores
        nothing and leaves an earlier pair as it was."""
        token, chat = token.strip(), chat.strip()
        refused = self._refusal(token, chat)
        if refused is not None:
            return self._saved_as(refused)
        earlier_token = self._spec.read_own(self._spec.token_secret)
        try:
            self._secrets.write(self._spec.token_secret, token)
            self._secrets.write(self._spec.chat_secret, chat)
        except SecretStoreUnavailableError:
            # The pair is one thing: a new token must not stay next to the old chat.
            self._put_back(self._spec.token_secret, earlier_token)
            return self._saved_as(TelegramSave.STORE_UNAVAILABLE)
        stored_token, stored_chat = self._stored()
        if not stored_token or not stored_chat:
            # Written, yet nothing reads back: the store cannot be read here, which is not
            # the same as another store answering first.
            return self._saved_as(TelegramSave.STORE_UNAVAILABLE)
        if (stored_token, stored_chat) != (token, chat):
            return self._saved_as(TelegramSave.OVERRIDDEN)
        return self._saved_as(TelegramSave.SAVED)

    def remove(self) -> TelegramRemoval:
        if not any(self._stored()):
            return self._removed_as(TelegramRemoval.NOTHING_STORED)
        earlier_token = self._spec.read_own(self._spec.token_secret)
        try:
            self._secrets.delete(self._spec.token_secret)
            self._secrets.delete(self._spec.chat_secret)
        except SecretStoreUnavailableError:
            self._put_back(self._spec.token_secret, earlier_token)
            return self._removed_as(TelegramRemoval.STORE_UNAVAILABLE)
        if any(self._stored()):
            return self._removed_as(TelegramRemoval.STILL_SET_ELSEWHERE)
        return self._removed_as(TelegramRemoval.REMOVED)

    def _put_back(self, name: str, earlier: str | None) -> None:
        """Returns one secret to what it was before a write or delete that failed half-way, so
        the pair stays what the page says ("nothing was saved"). Best effort: a store that is
        unavailable now may refuse this too, and that is told in the log."""
        try:
            if earlier is None:
                self._secrets.delete(name)
            else:
                self._secrets.write(name, earlier)
        except SecretStoreUnavailableError:
            logger.warning(
                "[alert-setup] %s credentials: the earlier value could not be put back",
                self._spec.channel_id,
            )

    def _refusal(self, token: str, chat: str) -> TelegramSave | None:
        if not token:
            return TelegramSave.EMPTY_TOKEN
        if not chat:
            return TelegramSave.EMPTY_CHAT
        if not self._spec.is_bot_token(token):
            return TelegramSave.NOT_A_BOT_TOKEN
        if not self._spec.is_chat_id(chat):
            return TelegramSave.NOT_A_CHAT_ID
        return None

    def _stored(self) -> tuple[str, str]:
        return (
            (self._secrets.read(self._spec.token_secret) or "").strip(),
            (self._secrets.read(self._spec.chat_secret) or "").strip(),
        )

    # The outcome is named in the text, never a value: no value derived from the secret store
    # reaches a log call (CodeQL py/clear-text-logging-sensitive-data).
    def _saved_as(self, outcome: TelegramSave) -> TelegramSave:
        logger.info(
            "[alert-setup] %s credentials save: %s",
            self._spec.channel_id,
            outcome.value,
        )
        return outcome

    def _removed_as(self, outcome: TelegramRemoval) -> TelegramRemoval:
        logger.info(
            "[alert-setup] %s credentials removal: %s",
            self._spec.channel_id,
            outcome.value,
        )
        return outcome
