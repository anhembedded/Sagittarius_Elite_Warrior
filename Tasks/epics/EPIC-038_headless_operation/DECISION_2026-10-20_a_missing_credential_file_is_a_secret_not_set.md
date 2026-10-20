# ADR — The unit loads the credentials directory, so a missing file is a secret that is not set

**Epic:** [EPIC-038](README.md)
**Date:** 2026-10-20
**Status:** Accepted
**Decided by:** 🤖 Agent decision, delegated by the owner (ONBOARDING §7) after his report of 2026-10-20 that every new secret forces a file before the restart (`status=243/CREDENTIALS`), and his approval to fix it with systemd's own mechanism, recommendations pre-approved through the coordinating session. The owner may veto; a veto reverts to the per-file `LoadCredential=` lines (the previous unit) or moves to `ImportCredential=` as D1 describes.
**Supersedes / superseded by (optional):** refines the unit of decision O3 of [the headless record](DECISION_2026-10-09_headless_operation.md) and of [the alerting record](../EPIC-036_alerting_module/DECISION_2026-10-15_walking_skeleton_and_headless_secrets.md) D3; the secrets stay systemd credentials.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree at the commit §1 names, or in the systemd 255 documentation cited |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |

## 1. Context
Read at `d2c7cad9`. ✅ `deploy/linux/sew-run.service` had one `LoadCredential=<name>:/etc/sew/credentials/<name>` line per secret (six). ✅ systemd refuses to start the unit when one source file is missing (`243/CREDENTIALS`, observed 2026-10-14 and again 2026-10-20 on systemd 255). ✅ An empty file already reads as "no key" (`secret_from_bytes`), so the files were placeholders only. Every new secret (the Discord webhook, the dead man's switch) therefore made the owner create a file before a restart.

Read in the systemd 255 manual (`systemd.exec(5)`) and its release notes:
- ✅ `LoadCredential=ID:PATH`, PATH an absolute **directory**: "every file in that directory (recursively) will be loaded as a separate credential. The ID for each credential will be the provided ID suffixed with `_$FILENAME` … symlinks will be ignored." The directory form arrived in systemd **251** (NEWS: "LoadCredential= now accepts a directory as the argument").
- ✅ `ImportCredential=GLOB` (systemd **254**): searches the system credentials, then `/etc/credstore/`, `/run/credstore/`, `/usr/lib/credstore/` and the `.encrypted` variants "in that order"; one trailing `*` only; **no rename form** in 255, so a credential keeps its file name; `LoadCredential=` wins on a clash.
- ❓→✅ not run: no systemd is PID 1 in the authoring container. The behaviour is read from the manual and proven on the server by the upgrade note's step 3.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **One line, `LoadCredential=sew:/etc/sew/credentials`, instead of `ImportCredential=`.** | Accepted | 🤖 Agent decision, delegated by the owner | A file that is not there is not loaded: a venue or feature without its file is off and the host starts. The directory `/etc/sew/credentials` is created by runbook §2 and exists on every server that ever started. Nothing moves: every existing file stays where it is. `ImportCredential=` also tolerates absence, but it would need all secrets moved to `/etc/credstore/` (a directory shared by every unit on the machine that imports a glob), a name prefix because 255 has no rename, systemd 254, and a migration that can leave the running server without keys. |
| D2 | **The app asks for `sew_<name>` first and the bare `<name>` second** (`SystemdCredentialStore`; the prefix is `UNIT_CREDENTIAL_ID`, one constant the unit is generated from). The prefixed file, if it exists, answers even when empty. | Accepted | 🤖 Agent decision, delegated by the owner | The directory form prefixes the credential's ID, so the app has to read the prefixed name; the bare fallback is what a unit with one line per file hands the process, so new code under the old unit (a half-finished upgrade, a rollback of the unit alone) keeps its keys. A name that is not a plain file name is refused before the prefix can hide it. |
| D3 | **`sew-key` writes the same directory and nothing else changes in it** (a test fixes its default to the unit's directory). `remove` still empties the two files rather than deleting them; only its messages stop calling a missing file a failure. | Accepted | 🤖 Agent decision, delegated by the owner | An emptied file reads as "no key" under both units, so a rollback to the per-file unit still starts. |
| D4 | **The unit is still generated** (`scripts/render_service_files.py`); the credential names remain read from the code, now for the header comment and the tests. | Accepted | 🤖 Agent decision, delegated by the owner | `test_service_files.py` fails on a hand edit and on a unit that names a single file again. |
| D5 | **The systemd floor in the runbook rises from 247 to 251.** | Accepted | 🤖 Agent decision, delegated by the owner | Ubuntu 22.04 ships 249 and can no longer run the unit; the owner's server (Ubuntu, 255) and 24.04 can. `ImportCredential=` would have raised it to 254. |
| D6 | **Upgrade order: stop, new code, new unit, check, check for a resetting drop-in, start.** | Accepted | 🤖 Agent decision, delegated by the owner | The new unit with the old code would find no key, because the old code asks for the bare name. A bare `LoadCredential=` left in a drop-in by the old runbook's testnet-only advice would empty the list, directory line included, and start the service with no credential and no error. Runbook §3 gives the commands, a check that lists the credential names the service would see, and `systemctl cat sew-run \| grep LoadCredential`. |

## 2a. Constitution check
Not a "🤖 Default, owner may veto" row of ONBOARDING §7 (it touches secrets handling, which that row excludes). It is an agent decision under the owner's explicit delegation of 2026-10-20, and he may still veto it; the check is recorded because it handles real-money keys.

| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | the unit having exactly one directory line, the store finding every name under the systemd name, and `sew-key`'s directory equalling the unit's are tests (`test_service_files.py`), not a runbook habit |
| P2 Verify, don't restate | ✅ | semantics read from the 255 manual and NEWS, quoted in §1; the live check is a command in the upgrade note |
| P3 A copy drifts | ✅ | the prefix is one constant (`UNIT_CREDENTIAL_ID`) that the generator and the store both import |
| P4 Green proves only what was tested | ✅ | systemd actually loading a directory and starting with a file absent is stated as unproven until the server runs step 3 (runbook §12) |
| P5 Apply before you invent | ✅ | systemd's own directory form; no new mechanism, store or script |
| P6 Fix the mechanism | ✅ | the cause was "a file per line"; the line count no longer grows with the secrets |
| P7 Seam now, variant later | ✅ | the store keeps the bare-name read, so `ImportCredential=` or an encrypted credential is a unit change plus a prefix constant |
| P8 Ratchets only fall | ✅ | two obsolete per-file tests are replaced by stricter ones on the same path; no baseline grew |
| P9 Decide alone | ✅ | decided under the owner's delegation; the one deviation from his wording (`ImportCredential=`) is named in D1 with the reason |
| P10 Pyramid and units | ✅ | unit tier; the shell snippets and `sew-key` are run for real under bash; `systemd-analyze verify` accepts the unit |
| P11 Prompt-grade artifacts | ✅ | the unit's header comment, the store's docstring and the runbook state the contract |
| Reversible; no dependency, setting, Engine or user data | ✅ | revert the commit and keep the files (they were never moved); a secret is never printed or moved |

## 3. Alternatives considered
| Alternative | Why it lost |
| :--- | :--- |
| `ImportCredential=sew.*` with the files under `/etc/credstore/sew.*` | Needs 254, a one-time move of every secret into a machine-wide store, and the same name prefix; the gain over the directory form is tolerating a missing *directory*, which the install already creates. Recorded as the veto path. |
| `LoadCredential=` per file with a `-` or `ConditionPathExists=` guard | systemd 255 has no optional `LoadCredential=`; a condition on the unit would skip the whole start. |
| `ExecStartPre=` that creates the missing files | Runs outside the sandbox the unit exists to enforce and writes `/etc/sew` from the unit. |
| Keep placeholders and automate their creation in `sew-key` | Leaves the failure for any secret added by hand or by a release; the unit, not a script, should not break. |

## 4. Open questions
None.

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1-D6 | [BOT-203](../../completed/BOT-203_a_missing_credential_file_is_a_secret_not_set.md) | Verified in unit tests; not on a real server | `tests/unit/scripts/test_service_files.py`, `tests/unit/support/secrets/test_systemd_credential_store.py`, `tests/unit/scripts/test_sew_key_*.py`, `tests/unit/scripts/test_runbook_shell_snippets.py` |
