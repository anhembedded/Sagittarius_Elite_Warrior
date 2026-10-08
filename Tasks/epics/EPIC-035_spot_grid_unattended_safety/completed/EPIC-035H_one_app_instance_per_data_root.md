# EPIC-035H — One app instance per data root

**Status:** ✅ Done (2026-10-08)
**Source:** the owner's Spot Grid audit, 2026-10-08, finding M6 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 2 of [EPIC-035](../README.md), approved 2026-10-08.
**Risk:** 🟡 — two instances place duplicate orders against one account
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), extended by this task
**Depends on:** None

---

## 1. Context and problem
**M6 — there is no single-instance lock. Verified ✅ on `be67b47`.** A search of `src/` and `scripts/` for `fcntl`, `msvcrt`, `flock` and lock files finds none; the symbol lease (`ITradingSession`'s claim) is a dict in one process, so a second process knows nothing of it. Two copies on one data root would both restore the same bots (`BotRestoreService` rewrites a RUNNING bot's file to RECOVERING), both lay ladders on the account and both answer the same fills.

**One thing the audit's cure left open: what "read-only" has to cover.** The restart rule at boot is itself a *write*: a second copy that merely started would rewrite the first copy's running bots. So read-only cannot be "orders are refused"; it has to cover the store, the boot, the runner and the venue client.

## 2. Acceptance criteria
- [x] A second app instance on the same data root detects the first through an exclusive lock file and opens read-only, saying so (window title, a notice, a log line).
- [x] The lock is released on a clean exit and on a crash (the OS releases it).
- [x] A read-only instance places and cancels nothing: every venue's trading client refuses a live order and every cancel; the bots module restores, watches and reconciles nothing; Start is refused by name; the bot store refuses every write.
- [x] Tests and sanity boots, each on its own temporary `SEW_DATA_ROOT`, never collide with each other or with a real instance (§3).

## 3. Design
- **Port** `IInstanceAccess` (`core/contracts`): `read_only` and `reason`. A module asks it and never learns how the answer was reached (seam now; a takeover or a viewer mode is one more implementation).
- **Lock** `infrastructure/single_instance/`: `InstanceAccess.acquire(lock_file)` takes an exclusive, non-blocking OS lock on `<data root>/state/instance.lock` (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows, one byte), keeps the handle, and is read-only when the lock is taken. No network, no pid file, no stale-file cleanup: the OS owns the lock, so a crash leaves nothing behind.
- **Who takes it — only the two entry points** (`main.py`'s and `app_bootstrapper.py`'s `main()`), once, before the graph is built, through `acquire_instance_access()` in the composition root. `create_app(config, instance=None)` and `build(instance=None)` take the answer as a **parameter** and default to writable, so a test or a sanity boot that builds the app in-process never contends for the lock; a guard (`test_only_the_entry_points_take_the_instance_lock.py`) keeps it that way. The lock file is under `data_root()`, so each pytest session's own `SEW_DATA_ROOT` (`EPIC-030M`) is its own lock; the self-check sanity test also gives its subprocess a root of its own.
- **Read-only, at the narrowest doors:** `ReadOnlyTradingClientFactory` over each venue's factory (every order of a bot, a person or the Emergency Stop is made by a client from it; a `VALIDATE_ONLY` test order, which places nothing, still passes); `ReadOnlyBotStore` over the store (every writer saves through it); `ReadOnlyBotRunner` over the runner (a Start is a named refusal, `BotRefusal.READ_ONLY_INSTANCE`, before its preconditions touch the venue); and `BotsModule.boot()` returns before the restart rule, the router and every watch.
- `IInstanceAccess` is bound by `create_app()` and **required** by the trading and bots bindings: an unbound port is the CS-003 defect, so there is no fallback to writable.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/core/contracts/i_instance_access.py`, `errors.py` | New port; `ReadOnlyInstanceError` |
| `src/infrastructure/single_instance/file_lock.py`, `instance_access.py` | New: the cross-platform lock and the access it backs |
| `src/shell/composition_root.py` | `acquire_instance_access()`, `instance_lock_file()`; `create_app(config, instance=None)` binds the port and logs the role |
| `src/main.py`, `src/presentation/ui/app_bootstrapper.py` | Acquire before the build, release in `finally`; the window says "(read-only)" and a notice tells why. `build()`'s remembered-state registrations moved to `remembered_state_wiring.py` (the file may only shrink: 513 → 470) |
| `src/modules/trading/adapters/read_only_trading_client_factory.py`, `composition/venue_assembly.py`, `adapter_bindings.py` | The read-only client factory; `SharedVenueInputs.instance` |
| `src/modules/bots/application/services/read_only_bot_store.py`, `read_only_bot_runner.py`, `composition/*_bindings.py`, `module.py`, `contracts/bot_command_result.py` | The read-only store and runner; `boot()` early return; `READ_ONLY_INSTANCE` |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md`, `Docs/VOCABULARY/README.md` | The journey; the term |
| tests (see §5); ten trading `test_module_*` files bind an unguarded access; `test_module_venue_contexts_binding.py` split (its `testnet`-flag test moved to `…_client_flag.py`, helpers to `venue_contexts_world.py`) to stay under 400 lines | |

## 5. Testing
| Criterion | Test | Tier |
| :--- | :--- | :--- |
| Second instance read-only | `test_a_second_instance_is_read_only`, `…does_not_take_the_lock_from_the_first`, `test_two_data_roots_never_collide`, `test_each_data_root_gets_its_own_first_instance` (`tests/unit/infrastructure/single_instance/`) | Unit |
| Lock dies with the process | `test_the_lock_dies_with_the_process` (a real second process, `kill()`ed), `test_a_clean_exit_of_the_holder_frees_the_lock_too` | Integration |
| Places and cancels nothing | `test_read_only_trading_client.py`, `test_venue_assembly_read_only.py` | Unit |
| Bots untouched | `test_read_only_bots.py`; `test_boot_leaves_a_running_bot_of_the_first_instance_as_it_is`, `test_a_second_instance_saves_no_bot`, `test_a_second_instance_starts_no_bot` | Unit · integration (real container) |
| It is the graph the app builds | `tests/unit/shell/test_a_second_instance_on_the_composed_app.py` | Unit (`create_app`) |
| No collision | `test_only_the_entry_points_take_the_instance_lock.py`; `test_a_second_real_process_on_the_same_data_root_boots_read_only`, `test_the_first_real_process_on_a_data_root_is_writable` | Guard · sanity (the real entry point, beside a real holder) |

## Implementation notes (written when done)

**Evidence.** Red first: the instance, lock-death and read-only-bots tests failed at collection (no port, no lock, no wrappers). Mutations measured on the finished code: `if False:` for the early return in `BotsModule.boot()` fails 2 tests; the store's, the venue assembly's and the lock's read-only branch each fail theirs (`try_lock_exclusive` always true fails 3).

**Deviations, for the owner.**
1. *"Opens read-only **or** refuses"* — it opens read-only, as the criteria say. Refusing to start would have been simpler; read-only keeps the Bots and Trading screens readable while the first copy trades.
2. *Start, Pause, Resume, Stop and Confirm resume* are answered with the named refusal `READ_ONLY_INSTANCE` carrying the instance's reason (the runner refuses; `BotCommandGate` turns the lifecycle commands' refusal into the value). *Create, Edit, Delete and Change venue* fail with the reason as an exception (the store refuses the write). How the Bots screen words either has not been looked at on a screen.
3. *Windows.* The lock uses `msvcrt.locking` on Windows. The POSIX path is proven, including by a killed process. **The Windows branch is neither run nor type-checked by any job:** CI is `ubuntu-latest` only and mypy skips the `sys.platform == "win32"` branch there. The owner should try it (start the app twice; kill the first with Task Manager; start a third).
3b. *What the lock guards is the data root, not the account* (review of PR 438, finding 5). Two checkouts are two data roots (the default root is the repository), `BOTS_STATE_DIR` can point outside the root, and a mainnet key in the OS keyring is shared across roots, so two copies on different roots can still lay two ladders on one account. The task says "per data root" and delivers that; scoping the lock to the account is an owner decision, not made here.
3c. *Leverage and margin mode* (review, finding 2): `FuturesAccountControl` bypasses the trading client, so it has a read-only wrapper of its own (`read_only_account_control.py`, one place with the client factory's: `read_only_guard.py`). Not traced: whether a read-only copy can reach `json_owner_inventory_checkpoints.py` (it writes under the data root) through `OwnerInventoryDeriver`.
3d. A lock call that fails for a reason other than "held" (a filesystem without `flock`) still gives a read-only copy but is logged with its errno and is not worded as another copy (review, finding 6).
4. *The user-data stream and market streams* of a read-only copy still open (they are reads). A second listen key on the same account is harmless to the first copy.
5. The trading-side wiring needed `IInstanceAccess` bound in every test container that registers the trading module (ten files, one line each): the port is required, not defaulted, on purpose.

**Pre-existing, seen and not touched.** `test_workbench_conformance.py::…[True-1024x700]` fails on `be67b47` in this Linux container (the backtest mode needs 706 px at 1024×700); `test_bots_selection` and one Futures-fills integration test failed once under parallel load and pass alone.

**Verification.** Commit tier PASS; `tests/unit/architecture` green; the changed trees green. The `-Full` gate is GitHub Actions' (see the pull request).
