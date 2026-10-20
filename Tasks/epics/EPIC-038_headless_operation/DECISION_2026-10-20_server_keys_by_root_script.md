# ADR — A server's keys are written by a root script; the app only checks them

**Epic:** [EPIC-038](README.md)
**Date:** 2026-10-20
**Status:** Accepted
**Decided by:** 🤖 Agent decision, delegated by the owner (ONBOARDING §7) after his instruction of 2026-10-20: *"co lam script de add key hay vps co tinh nang add key duoc ko? man hinh UI option da co tinh nang nay roi"* (can there be a script, or a VPS feature, to add keys? The desktop Options page already has this feature), and *"lam di"* (go ahead) to the design below. The owner may veto; a veto reverts to typing the files by hand, runbook section 3.
**Supersedes / superseded by (optional):** extends decision O3 of [the headless record](DECISION_2026-10-09_headless_operation.md) (Linux: systemd credentials); changes nothing in it.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree at the commit §1 names |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |

## 1. Context
Read at `c0a4dee`. ✅ The Options page's `EnrolKeyCommand` (`src/modules/trading/application/credentials/enrol_key/handler.py`) checks a key against the exchange and keeps it in the OS keyring or `secrets.local.json`; it refuses a venue whose key is an environment variable (`FROM_ENVIRONMENT`). ✅ A server's mainnet keys are systemd credentials read through `LoadCredential=` (`deploy/linux/sew-run.service`, `src/support/secrets/adapters/systemd_credential_store.py`), which the app reads and by design cannot write; its testnet keys are four environment names in `/etc/sew/sew.env`. ✅ The runbook (section 3) has the owner type `read -rsp` and `sudo tee` by hand, with no check of the key.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **The app writes no systemd credential and no `sew.env`.** A root-run script, `deploy/linux/sew-key`, writes them. | Accepted | 🤖 Agent decision, delegated by the owner | The app's stores stay read-only to it (O3); the privilege to write `/etc/sew` stays with root. |
| D2 | **The app only checks:** `main.py key check` reads the pair from standard input, asks each environment and says the venue; it writes nothing and prints neither value. | Accepted | 🤖 Agent decision, delegated by the owner | The check the Options page already runs is reused (`classify_key`), so a key is judged one way on the desktop and on the server. |
| D3 | **A key travels by shell builtins and pipes only:** `read -s`, `printf`, standard input; never an argument, an environment variable or a file argument. | Accepted | 🤖 Agent decision, delegated by the owner | Not in `ps`, not in `/proc/<pid>/environ`, not in a history. |
| D4 | **The operator types the venue's name to confirm** before anything is written. | Accepted | 🤖 Agent decision, delegated by the owner | The same consent as `--confirm-venue` (decision O8); a key for both mainnet venues is stored for the one typed. |
| D5 | **The probe logs no part of the key** (the first and last four characters it used to log). | Accepted | 🤖 Agent decision, delegated by the owner | `key check` runs as root on a server and a log outlives the terminal; the Options page's log loses the fingerprint, the environment and standing remain. |
| D6 | **Writes are atomic and private:** a temporary file beside the target under umask 077, `install -m` to the final mode (`0600` root credentials, `0640` root:sew `sew.env`), renamed over the target; the old key is put back if the second rename fails. The script never restarts the service. | Accepted | 🤖 Agent decision, delegated by the owner | A failure leaves the old key; the running host keeps its key until the operator restarts, and the printed next steps say the bots come back RECOVERING. |
| D7 | **A venue shadowed by an environment variable is refused** (the provider is environment-first for every venue). | Accepted | 🤖 Agent decision, delegated by the owner | The script would otherwise write a key the app never reads. |

## 2a. Constitution check (a default decision only)
Not a default decision (the owner approved the design, "lam di"); recorded anyway because the work handles real-money keys.

| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | the venue typed, the root check, the withdraw refusal and the shadow refusal are code (`test_sew_key_add.py`, `test_sew_key_remove_list_and_guards.py`, `test_key_check_cli.py`), not a habit |
| P2 Verify, don't restate | ✅ | the script reads the check's JSON; the venue names are validated against the known four before they build a path |
| P3 A copy drifts | ✅ | the classification is extracted once (`classify_key`), not copied; the exit codes are the table's |
| P4 Green proves only what was tested | ✅ | the real sudo hop, `chown root:sew`, systemd reading the files and a live key are stated as unproven in the task file |
| P5 Apply before you invent | ✅ | `LoadCredential`, `install -m`, write-temp-then-rename, `IKeyEnvironmentProbe`, `declare_cli`, `Report` all reused |
| P6 Fix the mechanism | ✅ | the question "which venue is this key" has one implementation |
| P7 Seam now, variant later | ✅ | a further store (Windows file) is a script variant; the check is unchanged |
| P8 Ratchets only fall | ✅ | the one replaced test (probe log) is stricter; no baseline, ceiling or allowlist grew |
| P9 Decide alone | ✅ | decided under the owner's delegation |
| P10 Pyramid and units | ✅ | unit tier, no network; the script is run for real under bash in `tmp_path` |
| P11 Prompt-grade artifacts | ✅ | the script header and the runbook state the contract |
| Reversible; no dependency, setting, Engine, user data | ✅ / real money | no dependency or Engine change; reverting is deleting the script and the command. It does handle real-money keys, which is why the owner approved the design |

## 3. Alternatives considered
| Alternative | Why it lost |
| :--- | :--- |
| The app writes the systemd credential files itself (a `key add` command) | The service account must not write `/etc/sew`; a writable credential directory for the service widens what a compromised bot can change. O3 made these stores read-only to the app on purpose. |
| `key add` run as root through the app | Boots the app as root, with the data root and its lock, to write a file. A bash script and a read-only check do the same with less privilege and no state. |
| Pass the key as an argument or an environment variable to `key check` | In `ps` and `/proc`; rejected outright. |
| Keep typing the files by hand | No check: a mistyped key, a testnet key in a mainnet file, a key that can withdraw and a file left `0644` are found at the next start. |
| A web page or a Discord command to add keys | A new input path and a secret in a channel (R11); out of the epic. |

## 4. Open questions
None.

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1-D7 | [BOT-200](../../completed/BOT-200_sew_key_adds_a_server_key_from_the_vps_command_line.md) | Verified in unit tests; not on a real VPS | `tests/unit/scripts/test_sew_key_add.py`, `tests/unit/scripts/test_sew_key_remove_list_and_guards.py`, `tests/unit/modules/trading/cli/` |
