"""`EPIC-038E` — every `ISecretStore` behaves the same where the port speaks.

One suite, run over each implementation (the keyring on a fake backend, systemd
credentials, the permission-checked file, the in-memory double), so a backend
added later is held to what the port promises and not to what its author
remembered. A backend that cannot be written to (systemd credentials are
provisioned by the unit file) says so with `SecretStoreUnavailableError`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    ISecretStore,
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.keyring_secret_store import (
    KeyringSecretStore,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.ordered_secret_stores import (
    OrderedSecretStores,
    SecretBackend,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.permission_checked_file_store import (
    PermissionCheckedFileStore,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.systemd_credential_store import (
    CREDENTIALS_DIRECTORY_ENV,
    SystemdCredentialStore,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_secret_file_check import (
    ISecretFileCheck,
    SecretFileVerdict,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore


class _MemoryKeyring(KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.entries: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.entries.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.entries[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self.entries:
            raise PasswordDeleteError("Password not found")
        del self.entries[(service, username)]


class _Accepts(ISecretFileCheck):
    def inspect(self, path: Path, descriptor: int) -> SecretFileVerdict:
        return SecretFileVerdict()


@dataclass(frozen=True)
class _Backend:
    """A store, how to put a value where it reads, and whether the app may write."""

    store: ISecretStore
    provision: Callable[[str, str], None]
    app_can_write: bool


def _in_memory(tmp_path: Path) -> _Backend:
    store = InMemorySecretStore()
    return _Backend(store, store.secrets.__setitem__, True)


def _keyring(tmp_path: Path) -> _Backend:
    store = KeyringSecretStore(_MemoryKeyring())
    return _Backend(store, store.write, True)


def _systemd(tmp_path: Path) -> _Backend:
    store = SystemdCredentialStore({CREDENTIALS_DIRECTORY_ENV: str(tmp_path)})
    return _Backend(
        store, lambda n, v: (tmp_path / n).write_text(v, encoding="utf-8"), False
    )


def _file(tmp_path: Path) -> _Backend:
    store = PermissionCheckedFileStore(tmp_path, (_Accepts(),))
    return _Backend(
        store, lambda n, v: (tmp_path / n).write_text(v, encoding="utf-8"), False
    )


def _ordered_writable(tmp_path: Path) -> _Backend:
    store = OrderedSecretStores.single(InMemorySecretStore())
    return _Backend(store, store.write, True)


def _ordered_provisioned(tmp_path: Path) -> _Backend:
    systemd = SystemdCredentialStore({CREDENTIALS_DIRECTORY_ENV: str(tmp_path)})
    store = OrderedSecretStores(
        (SecretBackend(CredentialsSource.SYSTEMD_CREDENTIAL, systemd),)
    )
    return _Backend(
        store, lambda n, v: (tmp_path / n).write_text(v, encoding="utf-8"), False
    )


_BACKENDS = {
    "ordered (writable)": _ordered_writable,
    "ordered (provisioned only)": _ordered_provisioned,
    "in-memory": _in_memory,
    "keyring": _keyring,
    "systemd": _systemd,
    "permission-checked file": _file,
}


@pytest.fixture(params=sorted(_BACKENDS))
def backend(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[_Backend]:
    yield _BACKENDS[request.param](tmp_path)


def test_every_secret_store_passes_the_same_contract_a_missing_secret_reads_none(
    backend: _Backend,
) -> None:
    assert backend.store.read("futures_mainnet_api_key") is None


def test_every_secret_store_passes_the_same_contract_a_provisioned_secret_reads_back(
    backend: _Backend,
) -> None:
    backend.provision("spot_mainnet_api_key", "fake-key-value")

    assert backend.store.read("spot_mainnet_api_key") == "fake-key-value"


@pytest.mark.parametrize("blank", ["", " ", "\n", " \t \r\n"])
def test_every_secret_store_passes_the_same_contract_a_blank_value_reads_absent(
    backend: _Backend, blank: str
) -> None:
    backend.provision("spot_mainnet_api_secret", blank)

    assert backend.store.read("spot_mainnet_api_secret") is None


@pytest.mark.parametrize(
    "name", ["../escape", "a/b", "a\\b", "", ".", "..", "nul\x00byte"]
)
def test_every_secret_store_passes_the_same_contract_a_name_that_is_not_a_name_reads_none(
    backend: _Backend, name: str
) -> None:
    assert backend.store.read(name) is None


def test_every_secret_store_passes_the_same_contract_a_write_either_lands_or_refuses(
    backend: _Backend,
) -> None:
    if backend.app_can_write:
        backend.store.write("k", "v")
        assert backend.store.read("k") == "v"
        backend.store.delete("k")
        assert backend.store.read("k") is None
        backend.store.delete("k")  # nothing stored: already as asked
    else:
        with pytest.raises(SecretStoreUnavailableError):
            backend.store.write("k", "v")
        with pytest.raises(SecretStoreUnavailableError):
            backend.store.delete("k")


@pytest.fixture(
    params=["systemd", "permission-checked file", "ordered (provisioned only)"]
)
def provisioned_elsewhere(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[_Backend]:
    yield _BACKENDS[request.param](tmp_path)


def test_every_secret_store_passes_the_same_contract_a_refusal_never_holds_the_value(
    provisioned_elsewhere: _Backend,
) -> None:
    with pytest.raises(SecretStoreUnavailableError) as raised:
        provisioned_elsewhere.store.write("k", "distinctive-secret-value")

    assert "distinctive-secret-value" not in str(raised.value)
    assert "distinctive-secret-value" not in repr(raised.value)
    assert not provisioned_elsewhere.app_can_write
