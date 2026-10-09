# EPIC-038E — A server can be given its exchange keys without a shell `export`

**Status:** 🔵 Planned — not started; waits for the owner's security decision O3
**Source:** the owner, 2026-10-09; the brief: *secrets go behind the existing `ISecretStore`; new backends are adapters (environment or systemd credentials, a permission-checked file); a backend that holds secrets needs the owner's security decision — present the options with a recommendation.* EPIC-036 plans to lift `ISecretStore` to `core/contracts`; coordinate, do not duplicate.
**Risk:** 🔴 — exchange keys; a wrong permission check or a logged value is a leaked key
**Complexity:** M — two adapters, a provider ordering, a permission checker per OS, contract tests
**Epic:** [EPIC-038](../README.md)
**SPEC:** [SPEC-003](../../../../Docs/SPEC/SPEC-003_check_the_exchange_connection.md) (the credentials step) is read; no journey changes for the GUI.
**Design:** [DESIGN §10](../DESIGN_2026-10-09_headless_operation.md) · **Research:** [§4, §6](../RESEARCH_2026-10-09_headless_operation.md) · **Decision:** [O3](../DECISION_2026-10-09_headless_operation.md)
**Depends on:** owner decision O3. Coordinates with [`EPIC-036A`](../../EPIC-036_alerting_module/incomplete/EPIC-036A_alerting_core.md) (N3: `ISecretStore` to `core/contracts`) — whichever lands first moves the port once; the other imports it.

---

## 1. Context and problem
Reads already work on a server: `EnvFirstCredentialsProvider` reads the environment first (`env_first_credentials_provider.py`), and `KeyringSecretStore` reads "nothing stored" with a single INFO line when no keyring exists (`keyring_secret_store.py:63-80`). What is missing is a way to **provision** a secret on a server that is better than putting it in a shell, an unprotected `.env`, or a process environment visible to the same user's tools. The `keyring` project's own recipe for headless Linux needs a D-Bus session and a password on stdin at every boot (R4), which is not unattended. systemd offers credentials (`LoadCredential`, `$CREDENTIALS_DIRECTORY`) that are not inherited by child processes and are access-checked by the kernel (R4). The port's own docstring names "an encrypted file for a machine with no keyring" as the plausible extension and records that the keyring was chosen over a file (D10 of `EPIC-034`).

## 2. Acceptance criteria
- [ ] The owner's decision O3 is recorded in the decision record before any adapter is built; the task implements only the backends it names (the recommendation is systemd credentials on Linux and the Credential Manager or a permission-checked file on Windows).
- [ ] `SystemdCredentialStore` implements `ISecretStore`: `read(name)` returns the file `$CREDENTIALS_DIRECTORY/<name>` stripped of one trailing newline, `None` when the variable or the file is missing; `write`/`delete` raise `SecretStoreUnavailableError` with a message saying credentials are provisioned by the unit file, not by the app.
- [ ] `PermissionCheckedFileStore` (if chosen) reads a file **outside the repository and the data root's tracked paths**; on POSIX it refuses (returns `None`, logs once at WARNING without the value or the path's contents) unless owner-only (mode `0600`/`0400`) and owned by the running user; on Windows it refuses unless the ACL grants only the service account and Administrators/SYSTEM. A refusal tells the owner the command to fix the permission.
- [ ] The lookup order stays environment first, then the configured stores in a documented order; adding a backend is one class and one entry in that order, with `EnvFirstCredentialsProvider` unchanged beyond reading the order from one place.
- [ ] No secret value appears in a log line, an error message, an exception string, a `repr`, the health snapshot, a plan file or `--json` output: a test sets a recognisable fake secret and greps all captured streams and the generated files.
- [ ] A file whose path lies inside a git work tree and is not ignored refuses with a clear message (plan and config files in version control must not hold secrets, R14).
- [ ] The key's withdrawal permission is not a store concern (it is `EPIC-038F`'s check), but `preflight` can state which backend a venue's key came from.
- [ ] A parametrised contract suite runs every `ISecretStore` implementation (keyring with a fake backend, systemd, file, in-memory) through the same behaviours: missing reads `None`, unavailable raises on write, empty and whitespace values read as absent.

## 3. Design
Adapters behind the existing port (dependency inversion), ordered by one list (open/closed), the same shape that put environment first and the keyring second. The permission check is its own collaborator (`SecretFilePermissionCheck`), one implementation per OS, so the store has one reason to change. Windows: `keyring` already ships a Windows Credential Manager backend; whether it works for a service account without an interactive profile is **unverified** — this task tests it on a Windows server before recommending it, and falls back to the permission-checked file.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/core/contracts/i_secret_store.py` | the port, moved once (with `EPIC-036A`) |
| `src/modules/trading/adapters/binance/mainnet/systemd_credential_store.py` (new) | the Linux backend |
| `src/modules/trading/adapters/binance/mainnet/permission_checked_file_store.py` (new) | the file backend |
| `src/support/binance_gateway/adapters/env_first_credentials_provider.py` | read the store order from one place |
| `tests/unit/.../test_secret_store_contract.py` (new) | the shared contract suite |

## 5. Testing
Tier: unit (`tmp_path`, a fake environment, a fake ACL reader).
- `test_systemd_credentials_read_from_the_credentials_directory` · `test_a_missing_credentials_directory_reads_none`
- `test_a_group_readable_secret_file_is_refused_without_logging_its_value` · `test_a_file_inside_a_git_work_tree_is_refused`
- `test_no_secret_value_reaches_any_log_error_repr_snapshot_or_json`
- `test_every_secret_store_passes_the_same_contract`
- `test_a_new_store_joins_by_one_entry_in_the_order`
Manual (owner's machines, testnet): a systemd unit with `LoadCredential=` starts `preflight` and finds the key; a Windows service account reads its key. Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. Blocked on O3.
