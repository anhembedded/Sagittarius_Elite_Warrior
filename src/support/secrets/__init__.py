"""Where a named secret comes from on this machine: a systemd credential, a
permission-checked file, or the operating system's keyring, asked in that order.

`EPIC-038E` built these stores for the mainnet exchange keys inside `trading`;
`EPIC-036G` (decision D3 of `EPIC-036`'s 2026-10-15 record) lifted them here so a
second module reads its own secret (the Discord webhook) the same way, without
importing `trading`'s adapters. Nothing here knows an exchange or a channel: a
secret is a name and a string, and the order is one list
(`secret_store_order.py`).

Who may import it: a module's `composition/` package, where adapters are chosen
(`tests/unit/architecture/boundaries/rules.py`, `_SECRETS_SUPPORT_ZONES`), and the
shell. A module's `application/` or `domain/` takes an `ISecretStore`
(`src/core/contracts/i_secret_store.py`) and never learns which store answered.

@par Extension cases
  · a new way to provision a secret (an encrypted file, a cloud secret manager):
    one class behind `ISecretStore` in `adapters/` and one entry in
    `secret_store_order._ORDER`;
  · a new rule a secret file must satisfy: one `ISecretFileCheck` in `adapters/`
    and one item in the list the file store is built with;
  · a new module that needs a secret: its `composition/` calls
    `build_secret_stores()` and reads its secret by name.

Capability: Read a named secret from wherever this host provides it (systemd credential, secret file, keyring)
    Also: secret store, credentials, LoadCredential, CREDENTIALS_DIRECTORY, keyring, webhook URL, API key, headless secret
    Use: build_secret_stores
    User: src/modules/trading/composition/adapter_bindings.py
    Status: stable
"""
