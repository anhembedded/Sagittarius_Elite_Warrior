"""Moves the Telegram bot token and chat id from the config file into the secret store, once
(`EPIC-036C1`, decision N3).

Until `EPIC-036B` they sat in `user_config.json` and `TelegramNotificationChannel` read them
there. A secret in a config file is copied by backups and pasted into bug reports, so the token
moves to the store the other channels use (`ISecretStore`: a systemd credential on a server, the
keyring on a desktop) and the file is cleared.

**The file is cleared only when the store gives the value back equal.** A store that cannot be
used leaves the file as it was (the token is not lost); one that accepts a write but answers with
another store's value (a provisioned systemd credential wins) leaves it too, because the value
the owner typed would then be nowhere. Each of the two keys moves on its own. The step runs at
every start and is idempotent: an empty key has nothing to move, so a second run changes
nothing and writes no file.

Nothing here names a value: an outcome is logged by key, never with the token or the chat id.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import IConfigReader
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_writer import IConfigWriter
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    ISecretStore,
    SecretStoreUnavailableError,
)

logger = logging.getLogger("App.Alerting")


@dataclass(frozen=True, slots=True)
class TelegramSecretNames:
    """The names the channel reads its two secrets under. Composition fills it from the adapter's
    constants, so this layer imports no adapter."""

    token: str
    chat: str


@dataclass(frozen=True, slots=True)
class _Move:
    config_key: str
    secret_name: str
    label: str


class TelegramConfigMigration:
    def __init__(
        self,
        reader: IConfigReader,
        writer: IConfigWriter,
        secrets: ISecretStore,
        names: TelegramSecretNames,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._secrets = secrets
        self._moves = (
            _Move(
                ConfigKeys.NOTIFICATIONS_TELEGRAM_BOT_TOKEN.value,
                names.token,
                "bot token",
            ),
            _Move(
                ConfigKeys.NOTIFICATIONS_TELEGRAM_CHAT_ID.value, names.chat, "chat id"
            ),
        )

    def run(self) -> None:
        moved = [move for move in self._moves if self._moved(move)]
        if not moved:
            return
        for move in moved:
            self._writer.set(move.config_key, "")
        try:
            self._writer.save()
        except OSError:
            logger.warning(
                "[alert-migration] telegram: stored in the secret store, but the config file "
                "could not be cleared (it is not writable); remove the old keys by hand"
            )
            return
        logger.info(
            "[alert-migration] telegram: moved %s from the config file to the secret store",
            ", ".join(move.label for move in moved),
        )

    def _moved(self, move: _Move) -> bool:
        value = str(self._reader.get(move.config_key, "") or "").strip()
        if not value:
            return False
        try:
            self._secrets.write(move.secret_name, value)
        except SecretStoreUnavailableError:
            logger.warning(
                "[alert-migration] telegram %s not migrated: no secret store can be used here "
                "(the value stays in the config file; on a server provision the credential %s)",
                move.label,
                move.secret_name,
            )
            return False
        if (self._secrets.read(move.secret_name) or "").strip() != value:
            logger.warning(
                "[alert-migration] telegram %s not migrated: another store answers for %s first "
                "(the value stays in the config file)",
                move.label,
                move.secret_name,
            )
            return False
        return True
