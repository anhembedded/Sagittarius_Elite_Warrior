# BOT-203 — A missing credential file means the secret is not set, never that the host does not start

**Status:** ✅ Done (2026-10-20)
**Board:** The unit loads the credentials directory with one `LoadCredential=sew:/etc/sew/credentials` line, so a file that was never created is a venue or feature that is off and the service still starts (it used to stop with `243/CREDENTIALS`); the app reads `sew_<name>` then the bare name, and no file moves ([decision](epics/EPIC-038_headless_operation/DECISION_2026-10-20_a_missing_credential_file_is_a_secret_not_set.md)).
**Source:** the owner, 2026-10-20: the unit lists six `LoadCredential=` lines and systemd refuses to start when one file is missing, though an empty file only means "not used"; every new secret forced him to create a file before restarting. He approved fixing it with systemd's own credential mechanism.
**Risk:** 🔴 — it changes how real-money keys reach the process; the failure to avoid is a server that restarts without its key (the new unit under the old code), a secret in the environment, an argument or a log, or a loosened file mode.
**Complexity:** S — the unit's one line, the store's name lookup, `sew-key` messages, tests and the runbook.
**Epic (optional):** [EPIC-038](../epics/EPIC-038_headless_operation/README.md)
**Depends on:** None (builds on `EPIC-038E`, `EPIC-038H`, `BOT-200`).

---

## 1. Context and problem
`deploy/linux/sew-run.service` named every secret file in its own `LoadCredential=` line. systemd cannot start a unit whose source file is missing (`243/CREDENTIALS`), so the runbook told the operator to create an empty placeholder for every venue and alert they did not use, and to create each new one before the release that named it was installed.

## 2. Acceptance criteria
- [x] The unit has exactly one `LoadCredential=` line, for the credentials directory, and none that names a file (`test_the_unit_loads_the_credentials_directory_and_no_file_a_missing_file_could_break`); it is still generated and equals its render.
- [x] Every secret the app reads (the four mainnet names, the Discord webhook, the dead man's switch URL) is found under the name systemd gives its file, `sew_<file>` (`test_every_secret_the_app_reads_is_found_under_the_name_systemd_gives_its_file`); a secret whose file does not exist reads as not set (`test_a_secret_whose_file_was_never_created_reads_as_not_set`).
- [x] An install with the new code and the old per-file unit keeps its keys: the bare name is read when the prefixed one is absent; the prefixed one wins and an empty prefixed file does not fall through (`test_systemd_credential_store.py`).
- [x] `sew-key` writes the directory the unit loads (`test_sew_key_writes_where_the_unit_reads`) and no longer calls a missing file a failed start (`test_list_names_a_missing_credential_file_as_not_set_and_not_as_a_failed_start`).
- [x] Secrets stay root-only (files `0600` root, read by systemd as root, handed to `User=sew` only), out of the environment, argv and logs: unchanged paths; `test_no_secret_value_reaches_any_output.py` still green.
- [x] The runbook has the upgrade note with the exact commands in order, no longer asks for placeholder files, and states the systemd floor (251).

## 3. Design
Agent decision, delegated by the owner (he may veto): [`DECISION_2026-10-20_a_missing_credential_file_is_a_secret_not_set.md`](../epics/EPIC-038_headless_operation/DECISION_2026-10-20_a_missing_credential_file_is_a_secret_not_set.md). `ImportCredential=` was checked against the 255 manual and not chosen: it needs systemd 254 and a move of every secret into `/etc/credstore`; the directory form needs neither.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/secrets/adapters/systemd_credential_store.py` | `UNIT_CREDENTIAL_ID`, `unit_credential_name`; `read` asks for the prefixed file then the bare one |
| `scripts/render_service_files.py`, `deploy/linux/sew-run.service` | one directory line, generated from `UNIT_CREDENTIAL_ID` |
| `deploy/linux/sew-key` | header and two messages |
| `Docs/OPERATIONS/headless_runbook.md`, `Docs/MODULES/alerting/07-deployment.md`, `src/modules/alerting/cli/alert_cli_handler.py` | the new route, the upgrade note, the `alert test` command |
| `tests/unit/scripts/`, `tests/unit/support/secrets/` | the proofs |

## 5. Testing
Unit tier, no network. `systemd-analyze verify` accepts the generated unit. Not run: a real systemd loading the directory (see the runbook §12; the upgrade note's step 3 proves it on the server).

## Implementation notes (written when done)
- The man page for 255 documents the directory form and the `<ID>_<file>` naming; the NEWS entry dates it to 251, which the runbook's floor now says.
- `sew-key remove` keeps emptying files instead of deleting them, so a rollback to the per-file unit still starts.
- Gate: the PR's `ci-local.ps1 -Full` run on its head is the authority; see the PR.
