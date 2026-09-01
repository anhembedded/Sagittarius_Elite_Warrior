"""EPIC-021B runnable milestone — see task §5.

Prints which source is currently winning for the Futures Testnet API
credentials (environment variable, the gitignored `secrets.local.json`
fallback, or none) and the resolved key/secret with the secret always
redacted — the same object `SettingsPresenter` uses to decide whether to
lock the Settings fields.

Exits 0 whether or not anything is configured — an unconfigured machine is a
valid, expected result at this milestone, not an error.

Run from the superproject root with the venv Python:
    PYTHONPATH=. Sagittarius_Elite_Warrior/.venv/bin/python \
        Sagittarius_Elite_Warrior/scripts/epic021b_credentials_probe.py
"""

from __future__ import annotations

from sagittarius_engine.utils.path_utils import PathUtils

from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.src.infrastructure.credentials.env_first_credentials_provider import (
    ENV_API_KEY,
    EnvFirstCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.infrastructure.credentials.secrets_file_source import (
    SecretsFileSource,
)

_SOURCE_LABEL = {
    CredentialsSource.ENV: f"ENV ({ENV_API_KEY})",
    CredentialsSource.FILE: "FILE (secrets.local.json)",
    CredentialsSource.NONE: "NONE",
}


def main() -> None:
    secrets_file_path = PathUtils.get_relative_path(
        __file__, "..", "src", "config", "secrets.local.json"
    )
    provider = EnvFirstCredentialsProvider(SecretsFileSource(secrets_file_path))
    resolution = provider.resolve()

    print(f"Nguồn: {_SOURCE_LABEL[resolution.source]}")
    if resolution.credentials is None:
        print(
            "Key:    (chưa cấu hình) — lấy key ở testnet.binancefuture.com, "
            f"rồi export {ENV_API_KEY} hoặc lưu qua màn Settings."
        )
        return

    print(f"repr(ExchangeCredentials) → {resolution.credentials!r}")
    leak_checks = {
        "repr": repr(resolution.credentials),
        "str": str(resolution.credentials),
        "f-string": f"{resolution.credentials}",
        "traceback": _render_in_a_traceback(resolution.credentials),
    }
    secret = resolution.credentials.api_secret
    results = " ".join(
        f"{name} {'✔' if secret not in text else '✘ LEAKED'}"
        for name, text in leak_checks.items()
    )
    print(f"Kiểm rò rỉ: {results}")


def _render_in_a_traceback(credentials: object) -> str:
    try:
        raise RuntimeError(f"probe-only exception carrying {credentials!r}")
    except RuntimeError as exc:
        return str(exc)


if __name__ == "__main__":
    main()
