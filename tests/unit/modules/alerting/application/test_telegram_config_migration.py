"""`EPIC-036C1` (N3) - the Telegram token and chat move from the config file into the secret
store once, and the file is cleared only after the store is read back equal."""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import IConfigReader
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_writer import IConfigWriter
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    ISecretStore,
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.telegram_channel import (
    TELEGRAM_CHAT_SECRET,
    TELEGRAM_TOKEN_SECRET,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.telegram_config_migration import (
    TelegramConfigMigration,
    TelegramSecretNames,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import (
    InMemorySecretStore,
    UnavailableSecretStore,
)

TOKEN = "987654321:Zq9-xY_wEbH00kT0k3nZq9xYwEbH00kT0k3n"  # noqa: S105 - made up
CHAT = "5550123"
TOKEN_KEY = ConfigKeys.NOTIFICATIONS_TELEGRAM_BOT_TOKEN.value
CHAT_KEY = ConfigKeys.NOTIFICATIONS_TELEGRAM_CHAT_ID.value


class _Config(IConfigReader, IConfigWriter):
    """The config file as one dict; `saved` counts the writes to disk."""

    def __init__(self, **values: str) -> None:
        self.values = dict(values)
        self.saved = 0

    def get(self, key: str, default: object = None) -> object:
        return self.values.get(key, default)

    def set(self, key: str, value: object) -> None:
        self.values[key] = str(value)

    def save(self) -> None:
        self.saved += 1


class _OverriddenStore(ISecretStore):
    """Another store answers first on this host (a systemd credential): a write is accepted
    but the read gives that store's own value."""

    def read(self, name: str) -> str | None:
        return "provisioned-elsewhere"

    def write(self, name: str, value: str) -> None:
        return None

    def delete(self, name: str) -> None:
        raise SecretStoreUnavailableError("read only")


def _migration(config: _Config, store: ISecretStore) -> TelegramConfigMigration:
    return TelegramConfigMigration(
        config,
        config,
        store,
        TelegramSecretNames(TELEGRAM_TOKEN_SECRET, TELEGRAM_CHAT_SECRET),
    )


def test_the_token_and_chat_move_to_the_store_and_leave_the_file() -> None:
    config = _Config(**{TOKEN_KEY: TOKEN, CHAT_KEY: CHAT})
    store = InMemorySecretStore()

    _migration(config, store).run()

    assert store.secrets == {TELEGRAM_TOKEN_SECRET: TOKEN, TELEGRAM_CHAT_SECRET: CHAT}
    assert config.values == {TOKEN_KEY: "", CHAT_KEY: ""}
    assert config.saved == 1


def test_a_second_run_changes_nothing() -> None:
    config = _Config(**{TOKEN_KEY: TOKEN, CHAT_KEY: CHAT})
    store = InMemorySecretStore()
    _migration(config, store).run()
    after_first = (dict(store.secrets), dict(config.values), config.saved)

    _migration(config, store).run()

    assert (store.secrets, config.values, config.saved) == after_first


def test_nothing_in_the_file_writes_nothing() -> None:
    config = _Config()
    store = InMemorySecretStore()

    _migration(config, store).run()

    assert store.secrets == {}
    assert config.saved == 0


def test_a_store_that_cannot_be_used_leaves_the_file_as_it_was(
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = _Config(**{TOKEN_KEY: TOKEN, CHAT_KEY: CHAT})

    with caplog.at_level(logging.INFO):
        _migration(config, UnavailableSecretStore()).run()

    assert config.values == {TOKEN_KEY: TOKEN, CHAT_KEY: CHAT}
    assert config.saved == 0
    assert any("not migrated" in r.getMessage() for r in caplog.records)


def test_a_store_that_does_not_give_the_value_back_leaves_the_file_as_it_was() -> None:
    """Written, but another store answers first: the token must not be lost from the file."""
    config = _Config(**{TOKEN_KEY: TOKEN, CHAT_KEY: CHAT})

    _migration(config, _OverriddenStore()).run()

    assert config.values == {TOKEN_KEY: TOKEN, CHAT_KEY: CHAT}
    assert config.saved == 0


def test_only_the_key_that_is_set_moves() -> None:
    config = _Config(**{CHAT_KEY: CHAT})
    store = InMemorySecretStore()

    _migration(config, store).run()

    assert store.secrets == {TELEGRAM_CHAT_SECRET: CHAT}
    assert config.values[CHAT_KEY] == ""


def test_neither_value_reaches_a_log_line(caplog: pytest.LogCaptureFixture) -> None:
    config = _Config(**{TOKEN_KEY: TOKEN, CHAT_KEY: CHAT})

    with caplog.at_level(logging.DEBUG):
        _migration(config, InMemorySecretStore()).run()
        _migration(_Config(**{TOKEN_KEY: TOKEN}), UnavailableSecretStore()).run()

    text = "\n".join(record.getMessage() for record in caplog.records)
    assert TOKEN not in text
    assert TOKEN.split(":")[1] not in text
    assert CHAT not in text


def test_a_file_that_cannot_be_written_keeps_the_secret_in_the_store_and_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _ReadOnlyFile(_Config):
        def save(self) -> None:
            raise OSError("read-only file system")

    config = _ReadOnlyFile(**{TOKEN_KEY: TOKEN, CHAT_KEY: CHAT})
    store = InMemorySecretStore()

    with caplog.at_level(logging.INFO):
        _migration(config, store).run()

    assert store.secrets[TELEGRAM_TOKEN_SECRET] == TOKEN
    assert any("could not be cleared" in r.getMessage() for r in caplog.records)


def test_a_run_with_no_writable_config_file_keeps_the_secret_and_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The Engine's `save()` raises `ValueError`, not `OSError`, when no writable file was loaded
    (a headless run with only the defaults)."""

    class _NoWritableFile(_Config):
        def save(self) -> None:
            raise ValueError("requires a writable source")

    config = _NoWritableFile(**{TOKEN_KEY: TOKEN, CHAT_KEY: CHAT})
    store = InMemorySecretStore()

    with caplog.at_level(logging.INFO):
        _migration(config, store).run()

    assert store.secrets[TELEGRAM_TOKEN_SECRET] == TOKEN
    assert any("could not be cleared" in r.getMessage() for r in caplog.records)
