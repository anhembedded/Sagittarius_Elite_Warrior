# BOT-200 — A key is added on the VPS by a root script, checked by `key check`

**Status:** ✅ Done (2026-10-20)
**Board:** A server's Binance key is now added with `sudo sew-key add`: the app only checks it (`key check`, stdin only, writes nothing) and a root script writes the systemd credential files or `sew.env`; the app never writes a systemd credential ([decision](epics/EPIC-038_headless_operation/DECISION_2026-10-20_server_keys_by_root_script.md)).
**Source:** the owner, 2026-10-20: *"co lam script de add key hay vps co tinh nang add key duoc ko? man hinh UI option da co tinh nang nay roi"* (can there be a script, or a VPS feature, to add keys? The desktop Options page already has this feature), then *"lam di"* (go ahead) to the design below.
**Risk:** 🔴 — it handles real-money API keys; the failure to avoid is a key in an argument, a log, an output or a leftover file, and a wrong file mode.
**Complexity:** M — one read-only command with a use case, one bash script, their tests and the runbook.
**Epic (optional):** [EPIC-038](../epics/EPIC-038_headless_operation/README.md)
**SPEC (optional):** [SPEC-015](../../Docs/SPEC/SPEC-015_run_the_bots_headless.md)
**Depends on:** None (builds on `BUG-176` enrolment and `EPIC-038E` secret stores).

---

## 1. Context and problem
On the VPS the owner types `read -rsp` and `sudo tee` by hand into `/etc/sew/credentials/<venue>_api_key` and `_api_secret` (mainnet: systemd `LoadCredential=` files, root `0600`) or edits `/etc/sew/sew.env` (testnet, four names). The Options page's `EnrolKeyCommand` is Qt-only and writes the OS keyring or `secrets.local.json`, never these stores: systemd credentials are read-only to the app by design (`EPIC-038E`), and a venue whose key is an environment variable is never written (`EnrolKeyCommandHandler`, `EnrolmentRefusal.FROM_ENVIRONMENT`). A hand-typed file has no check: a mistyped key, a testnet key in a mainnet file, a key that can withdraw, a file left `0644` are found at the next start.

## 2. Acceptance criteria
- [x] `main.py key check` reads the key then the secret from standard input only (two lines; a prompt with no echo on a terminal), asks each environment through `IKeyEnvironmentProbe`, stops at the first that accepts, and reports the venue(s): Spot or Futures, Testnet or Mainnet. No argument, environment variable or file carries a value (`test_no_argument_can_carry_a_key_or_a_secret`, `test_key_stdin.py`).
- [x] It refuses, with a reason and an exit status from the existing table: a mainnet key that can withdraw (5), a key that may trade nothing (5), a key no environment accepts with the per-environment reasons (5, or 6 when an environment did not answer), an empty value or a character a Binance key never has (2) (`test_key_check_cli.py`, `test_check_key_query.py`).
- [x] Its text and `--json` output and the log of every outcome hold neither the key nor the secret (`test_neither_the_key_nor_the_secret_reaches_the_output_or_the_log_in_any_outcome`, 11 outcomes x 2 formats, a sentinel in both).
- [x] It is read-only (`"read_only": true`, builds only `trading`): no lock, no writable data root, writes nothing (`test_key_check_needs_no_writable_data_root_and_builds_only_trading`).
- [x] `deploy/linux/sew-key add [venue]` prompts with `read -rsp`, pipes the pair to `key check` run as `sew`, shows the venue it reports, asks the operator to type the venue, and only then writes: mainnet to `/etc/sew/credentials/<venue>_api_key` and `_api_secret` (`0600` root), testnet to the venue's two lines of `sew.env` (`0640` root:sew, every other line kept), by a temporary file in the same directory renamed over the target; a failure leaves the old key. It refuses when an environment variable would shadow the venue (`test_sew_key_add.py`, `test_sew_key_remove_list_and_guards.py`).
- [x] `remove <venue>` empties the mainnet files (never deletes) or deletes the venue's two `sew.env` lines, after the venue is typed; `list` prints presence, mode and owner and no value, length, prefix or hash; after `add`/`remove` the next steps (restart, RECOVERING, `bot resume`) are printed and nothing is restarted; the script refuses unless root and when the credentials directory is missing.
- [x] The runbook's section 3 leads with the script and keeps the manual commands as the fallback.

## 3. Design
**Agent decision, delegated by the owner** ("lam di"; he may veto): [`DECISION_2026-10-20_server_keys_by_root_script.md`](../epics/EPIC-038_headless_operation/DECISION_2026-10-20_server_keys_by_root_script.md). The app never writes a systemd credential; a root script writes them and the app only checks.

- `key check` is `CheckKeyQuery` over `classify_key`, the function `EnrolKeyCommandHandler` already needed (ask each environment, stop at the first accepting, decide the venues from the permissions). Extracted, not copied, so the Options page and the command line cannot disagree about a key; the enrolment's behaviour is unchanged (`test_key_use_cases.py` green).
- The command offers `--json`/`--format` and nothing else: the key can only arrive on standard input.
- Exit statuses are the existing ones (`exit_codes.md`, decision D9): 2 the input cannot be a key, 5 only the operator can fix it (withdraws, may not trade, refused), 6 an environment did not answer. No new code.
- The script reads the check's `--json` (`data.venues`, `data.message`) with the service venv's Python in isolated mode, so it adds no tool to the server. Venue names are checked against the four known ones before they build a path.
- A key may be for both mainnet venues (a Spot and Futures key): the operator types the one to store it for, which is also the confirmation.

**One behaviour change outside the new command, deliberate:** `BinanceKeyEnvironmentProbe` logged the key's first and last four characters (`key_fingerprint`). `key check` runs as root on a server and a log outlives the terminal, so the probe now logs the environment and the standing only. The test that pinned the fingerprint is replaced by one that pins its absence (P8: stronger coverage of the same path).

## 3a. Reuse
`IKeyEnvironmentProbe` and `EnrolKeyCommandHandler`'s logic (extracted to `classify_key`); `ICliRegistry`/`CliCommandDescriptor`, `cli_commands.json`, `command_is_read_only`/`command_needed_modules`; `IReportPrinter`, `Report`, `CliOutcome`/`ExitCode`; `ICommandDispatcher`; the runbook's `$M` invocation and `read -rsp`/`install` idioms. Searched `capabilities.md` for "credentials/secret store": `build_secret_stores` reads secrets and is not used, because the script writes them and the app must not.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/application/credentials/classify_key.py` | the shared "which venues is this key for" |
| `src/modules/trading/application/credentials/enrol_key/handler.py` | calls `classify_key`; behaviour unchanged |
| `src/modules/trading/contracts/key_check.py` | `KeyCheck`, `KeyCheckRefusal` |
| `src/modules/trading/application/queries/check_key/` | `CheckKeyQuery` and its handler; bound in `composition/query_bindings.py` |
| `src/modules/trading/cli/` | `key_stdin.py`, `key_check_report.py`, `key_cli_handler.py`, `cli_declarations.py`; declared by `TradingModule.declare_cli` |
| `src/modules/trading/adapters/binance/key_environment_probe.py` | the log line names no part of the key |
| `src/config/cli_commands.json`, `src/support/cli_host/exit_code_table.py`, `Docs/OPERATIONS/exit_codes.md` | `key check` declared; listed under exit 5 |
| `deploy/linux/sew-key` | the root script |
| `Docs/OPERATIONS/headless_runbook.md` | section 3 |
| `tests/unit/modules/trading/cli/`, `tests/unit/scripts/test_sew_key_add.py`, `tests/unit/scripts/test_sew_key_remove_list_and_guards.py`, `tests/unit/support/cli_host/test_command_access.py`, `tests/unit/modules/trading/adapters/binance/test_key_environment_probe.py` | the proofs |

## 5. Testing
Unit tier, no network (`ci-rule.md` §2). Every criterion above names its test. The script is run for real under bash against a temp directory with a stub standing in for `key check`; the stub records its argv and stdin, proving the pair travelled by standard input and by no argument. Mutation checks done by hand: logging `credentials.api_key` in `run_key_check` turns the sentinel test red; removing `mv -T` turns the directory-target test red; skipping the venue confirmation turns the mismatch test red. Also run once by hand end to end against the real app (a `sudo` shim dropping `-u sew`): a fake alphanumeric key reached the exchange, was refused by all three environments and the script wrote nothing. **Not proven here:** the real `sudo -u sew` hop, the `chown` to `root:sew`, systemd reading a file the script wrote, and a real Binance key; the owner's first run on the VPS is that check.

## 6. Docs touched
`Docs/OPERATIONS/headless_runbook.md` section 3 (the script first, manual commands kept) and section 7's neighbour table is unchanged; `Docs/OPERATIONS/exit_codes.md` (generated: `key check` under exit 5). `Docs/MODULES/`: no `trading` folder exists, so no module design file applies.

## Implementation notes (written when done)
- The shared extraction kept `EnrolKeyCommandHandler`'s results identical; its existing tests are untouched and green.
- `src/modules/trading/module.py` sat at exactly the 400-line ceiling (`test_god_files_only_shrink.py`): the declaration lives in `cli/cli_declarations.py` and the module's historical docstring paragraph was condensed to make room, with no fact dropped.
- `mv` was found to move a file *into* a target directory; the script uses `mv -fT` and checks the targets are not directories first. A secret that cannot be published puts the old key back (`test_a_secret_that_cannot_be_published_puts_the_old_key_back`).
- Gate: the PR's `ci-local.ps1 -Full` run on its head is the authority; see the PR.
