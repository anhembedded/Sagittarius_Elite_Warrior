"""Save, remove and describe the Discord webhook the Options page manages (`EPIC-036D1`).

The one write path the app has for a channel's secret. The webhook URL is the
secret (N3): whoever holds it can post to the owner's channel. So this class takes it
in, validates it, hands it to the store and gives nothing of it back. An outcome is an
enum, a state carries four characters of the token so the owner can tell which webhook
is saved, and no log line or exception text it makes holds the URL.

**What the app can write is the keyring** (`OrderedSecretStores` marks one writable
backend). On a host that provisions the webhook elsewhere (a systemd credential, a
secret file) that provisioned value is read first, so a save would change nothing the
channel uses: the read-back after the write catches it (`OVERRIDDEN`), and the page
says so instead of "saved".

**A saved webhook takes effect for sending without a restart** (the channel reads its
secret at each send), **but the Discord lane starts only at boot**: a first save or a
removal changes whether the run has the lane, so `DiscordChannelState.running` is the
catalog's answer and the page words the restart (`Docs/MODULES/alerting/06-runtime.md`).
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

#: How many characters of the token the state shows, so the owner can tell two
#: webhooks apart. The token is far longer; four are not a way to guess it.
HINT_CHARS = 4


@dataclass(frozen=True, slots=True)
class WebhookChannelSpec:
    """What names the channel and its secret, and what a usable value looks like.
    Composition fills it from the adapter's constants, so this layer imports no adapter."""

    channel_id: str
    secret_name: str
    is_webhook_url: Callable[[str], bool]


class WebhookSave(Enum):
    SAVED = "saved"
    EMPTY = "empty"
    NOT_A_DISCORD_WEBHOOK = "not a discord webhook"
    STORE_UNAVAILABLE = "store unavailable"
    #: Written, but another store answers first on this host, so it is not the one in use.
    OVERRIDDEN = "overridden by another store"


class WebhookRemoval(Enum):
    REMOVED = "removed"
    NOTHING_STORED = "nothing stored"
    STORE_UNAVAILABLE = "store unavailable"
    #: The app's store forgot it, but another store still holds one.
    STILL_SET_ELSEWHERE = "still set by another store"


@dataclass(frozen=True, slots=True)
class DiscordChannelState:
    #: Some store holds a value under the secret's name.
    stored: bool
    #: ... and the value is a webhook URL the channel would post to.
    usable: bool
    #: The last characters of a usable webhook's token; "" otherwise. Never the URL.
    hint: str
    #: This run has the channel (it was configured when the app booted).
    running: bool


class DiscordWebhookSetup:
    def __init__(
        self,
        secrets: ISecretStore,
        spec: WebhookChannelSpec,
        catalog: IAlertChannelCatalog,
    ) -> None:
        self._secrets = secrets
        self._spec = spec
        self._catalog = catalog

    @property
    def channel_id(self) -> str:
        """The id of the channel this sets up: what `IChannelEnabling` switches."""
        return self._spec.channel_id

    def state(self) -> DiscordChannelState:
        stored = self._stored()
        usable = bool(stored) and self._spec.is_webhook_url(stored)
        return DiscordChannelState(
            stored=bool(stored),
            usable=usable,
            hint=stored[-HINT_CHARS:] if usable else "",
            running=self._spec.channel_id in self._catalog.channel_ids(),
        )

    def save(self, value: str) -> WebhookSave:
        """Stores `value` as the webhook when it is a webhook URL; otherwise stores
        nothing and leaves an earlier webhook as it was."""
        url = value.strip()
        if not url:
            return self._saved_as(WebhookSave.EMPTY)
        if not self._spec.is_webhook_url(url):
            return self._saved_as(WebhookSave.NOT_A_DISCORD_WEBHOOK)
        try:
            self._secrets.write(self._spec.secret_name, url)
        except SecretStoreUnavailableError:
            return self._saved_as(WebhookSave.STORE_UNAVAILABLE)
        stored = self._stored()
        if not stored:
            # Written, yet nothing reads back: the store cannot be read here, which is
            # not the same as another store answering first.
            return self._saved_as(WebhookSave.STORE_UNAVAILABLE)
        if stored != url:
            return self._saved_as(WebhookSave.OVERRIDDEN)
        return self._saved_as(WebhookSave.SAVED)

    def remove(self) -> WebhookRemoval:
        if not self._stored():
            return self._removed_as(WebhookRemoval.NOTHING_STORED)
        try:
            self._secrets.delete(self._spec.secret_name)
        except SecretStoreUnavailableError:
            return self._removed_as(WebhookRemoval.STORE_UNAVAILABLE)
        if self._stored():
            return self._removed_as(WebhookRemoval.STILL_SET_ELSEWHERE)
        return self._removed_as(WebhookRemoval.REMOVED)

    def _stored(self) -> str:
        return (self._secrets.read(self._spec.secret_name) or "").strip()

    # The outcome is named in the text, never the value: no value derived from the
    # secret store reaches a log call (CodeQL py/clear-text-logging-sensitive-data).
    def _saved_as(self, outcome: WebhookSave) -> WebhookSave:
        logger.info(
            "[alert-setup] %s webhook save: %s", self._spec.channel_id, outcome.value
        )
        return outcome

    def _removed_as(self, outcome: WebhookRemoval) -> WebhookRemoval:
        logger.info(
            "[alert-setup] %s webhook removal: %s", self._spec.channel_id, outcome.value
        )
        return outcome
