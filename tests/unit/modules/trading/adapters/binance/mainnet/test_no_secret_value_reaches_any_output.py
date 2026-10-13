"""`EPIC-038E` — a recognisable fake secret goes through every backend, and
nothing a person or a monitor can read holds it: no log record, no exception
string, no `repr`, no pre-flight text or `--json`, no file the run wrote.

Every scenario first asserts the secret **was resolved** through the backend
under test; absence from the output is meaningless otherwise (`EPIC-038G`).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.check_result import CheckStatus
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import PreflightScope
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_report import (
    preflight_report,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.ordered_secret_stores import (
    OrderedSecretStores,
    SecretBackend,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.permission_checked_file_store import (
    PermissionCheckedFileStore,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.posix_secret_file_permission_check import (
    FileFacts,
    PosixSecretFilePermissionCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.systemd_credential_store import (
    CREDENTIALS_DIRECTORY_ENV,
    SystemdCredentialStore,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.credentials_present_check import (
    CredentialsPresentCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_secret_file_check import (
    ISecretFileCheck,
    SecretFileVerdict,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    MainnetCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.json_report_renderer import (
    JsonReportRenderer,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.text_report_renderer import (
    TextReportRenderer,
)

from ...preflight.preflight_world import reads_over, venue

CANARY_KEY = "CANARY-KEY-038e-5f1c9e0a-never-log-me"
CANARY_SECRET = "CANARY-SECRET-038e-b27d44c1-never-log-me"  # noqa: S105 - a fake, planted to prove it is never logged
VENUE = TradingVenue.SPOT_MAINNET
KEY_NAME, SECRET_NAME = f"{VENUE.value}_api_key", f"{VENUE.value}_api_secret"


class _Accepts(ISecretFileCheck):
    def inspect(self, path: Path) -> SecretFileVerdict:
        return SecretFileVerdict()


def _plant(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / KEY_NAME).write_text(f"{CANARY_KEY}\n", encoding="utf-8")
    (directory / SECRET_NAME).write_text(f"{CANARY_SECRET}\n", encoding="utf-8")


def _systemd(directory: Path) -> OrderedSecretStores:
    store = SystemdCredentialStore({CREDENTIALS_DIRECTORY_ENV: str(directory)})
    return OrderedSecretStores(
        (SecretBackend(CredentialsSource.SYSTEMD_CREDENTIAL, store),)
    )


def _file(directory: Path) -> OrderedSecretStores:
    store = PermissionCheckedFileStore(directory, (_Accepts(),))
    return OrderedSecretStores((SecretBackend(CredentialsSource.SECRET_FILE, store),))


def _group_readable_file(directory: Path) -> OrderedSecretStores:
    check = PosixSecretFilePermissionCheck(
        lambda _: FileFacts(mode=0o640, owner_id=7, is_regular=True), lambda: 7
    )
    store = PermissionCheckedFileStore(directory, (check,))
    return OrderedSecretStores((SecretBackend(CredentialsSource.SECRET_FILE, store),))


_RESOLVED_THROUGH = [
    ("systemd credential", _systemd, CredentialsSource.SYSTEMD_CREDENTIAL),
    ("permission-checked file", _file, CredentialsSource.SECRET_FILE),
]


def _everything_a_person_can_read(
    stores: OrderedSecretStores, caplog: pytest.LogCaptureFixture
) -> str:
    provider = MainnetCredentialsProvider(stores, VENUE)
    resolved = provider.resolve()
    seen: list[str] = [repr(resolved), str(resolved), repr(provider), repr(stores)]
    seen += [repr(b) for b in stores.backends]
    seen += [repr(b.store) for b in stores.backends]
    if resolved.credentials is not None:
        seen += [repr(resolved.credentials), str(resolved.credentials)]
    for attempt in (
        lambda: provider.save_to_file(CANARY_KEY, CANARY_SECRET),
        provider.remove_stored,
    ):
        try:
            attempt()
        except SecretStoreUnavailableError as raised:
            seen += [str(raised), repr(raised)]

    reads = reads_over(venue(VENUE, credentials=provider))
    result = CredentialsPresentCheck(reads).run(PreflightScope())
    report = preflight_report((result,))
    seen += [TextReportRenderer().render(report), JsonReportRenderer().render(report)]
    json.loads(JsonReportRenderer().render(report))  # --json stays parseable
    seen += [caplog.text, repr(caplog.records)]
    return "\n".join(seen)


@pytest.mark.parametrize(
    ("backend", "build", "source"),
    _RESOLVED_THROUGH,
    ids=[name for name, _, _ in _RESOLVED_THROUGH],
)
def test_no_secret_value_reaches_any_log_error_repr_snapshot_or_json(
    backend: str,
    build: object,
    source: CredentialsSource,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _plant(tmp_path)
    stores = build(tmp_path)  # type: ignore[operator]

    with caplog.at_level(logging.DEBUG):
        resolved = MainnetCredentialsProvider(stores, VENUE).resolve()
        # Positive proof first: the canary was resolved through this backend.
        assert resolved.source is source, backend
        assert resolved.credentials is not None
        assert resolved.credentials.api_secret == CANARY_SECRET
        output = _everything_a_person_can_read(stores, caplog)

    assert source.value in output  # the preflight names the backend...
    assert CANARY_KEY not in output  # ...and never the value
    assert CANARY_SECRET not in output


def test_a_refused_file_leaks_nothing_and_the_check_names_no_key(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _plant(tmp_path)
    stores = _group_readable_file(tmp_path)

    with caplog.at_level(logging.DEBUG):
        resolved = MainnetCredentialsProvider(stores, VENUE).resolve()
        assert resolved.credentials is None  # refused, so not resolved
        assert resolved.source is CredentialsSource.NONE
        output = _everything_a_person_can_read(stores, caplog)

    refusals = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert refusals, "the refusal was not logged"
    assert "chmod 600" in output  # the command that fixes the permission
    assert CANARY_KEY not in output
    assert CANARY_SECRET not in output
    result = CredentialsPresentCheck(
        reads_over(venue(VENUE, credentials=MainnetCredentialsProvider(stores, VENUE)))
    ).run(PreflightScope())
    assert result.status is CheckStatus.FAIL


def test_nothing_the_stores_do_writes_a_file(tmp_path: Path) -> None:
    _plant(tmp_path)
    before = sorted(p.name for p in tmp_path.rglob("*"))

    for stores in (_systemd(tmp_path), _file(tmp_path)):
        provider = MainnetCredentialsProvider(stores, VENUE)
        provider.resolve()
        with pytest.raises(SecretStoreUnavailableError):
            provider.save_to_file(CANARY_KEY, CANARY_SECRET)

    assert sorted(p.name for p in tmp_path.rglob("*")) == before
    for path in tmp_path.iterdir():
        assert path.read_text(encoding="utf-8") in (
            f"{CANARY_KEY}\n",
            f"{CANARY_SECRET}\n",
        )  # untouched
