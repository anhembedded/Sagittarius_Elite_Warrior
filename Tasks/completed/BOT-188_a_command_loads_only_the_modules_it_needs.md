# BOT-188 — A command loads only the modules and libraries it needs, so `bot list` stops paying seconds of import work before its first line

**Status:** ✅ Done (2026-10-17)
**Board:** Cause: `bot list` imported every bounded context, the exchange SDK (`dateparser`, `aiohttp`, `requests`) and `pyarrow` to read a file, ~3 s on the VPS before the first log line ([`PRO-014`](proposal/PRO-014.md)). Fix: `cli_commands.json` `"modules"` per command + `select_modules` (a context comes with its suppliers) + `ModuleEntry`/`Deferred` for classes and adapters that import the SDK; `bot list` is 1.8x faster by wall clock in the CI container (2.07-2.12 s to 1.16-1.18 s median), short of the 2x asked; not yet measured on the VPS.
**Source:** The owner, 2026-10-17: *"không, là 2. liền, lưu vào proposal"* ("no, option 2, right away, save it as a proposal"), after measuring `main.py bot list` at 3.7 s on the VPS of which the application is 0.057 s. Accepted proposal: [`PRO-014`](../proposal/PRO-014.md).
**Risk:** 🟡 — it changes how the composition root is built for every command and for the desktop application (which still gets every context). Real-money paths are untouched: `run`, `trade-once` and the GUI declare nothing and build everything, and the order and stream adapters are the same classes, imported later.
**Complexity:** L — a composition-root seam, three composition files in two contexts, one boot split, six guards updated, one new guard, one measuring script.
**Depends on:** None. Merged with master at `f1aec4e` (EPIC-038L `bot edit`, BOT-187 `bot order`).

---

## 1. Context and problem
At `db5a961`, 2026-10-17, `main.py bot list` took 3.7 s on the owner's VPS; composing, querying and disposing took 0.057 s, `python -c pass` 0.033 s. `-X importtime` put the rest in `shell.composition_root` (2.03 s cumulative: `shell.modules` 1.64 s, `bots.module` 0.70 s, `trading.module` 0.37 s) and `market_data.cli.stream_cmd` (0.94 s, of which the `binance` SDK 0.71 s through `failure_exit_code`). See [`PRO-014`](../proposal/PRO-014.md) §1 for the table and the repository facts.

## 2. Acceptance criteria
- [x] A command loads only the contexts it declares and their suppliers. Evidence: `test_a_read_command_imports_only_what_it_needs_process.py` (fresh interpreter): `bot list`/`bot show` import `bots`, `trading`, `market_data` and none of `strategy`, `backtesting`, `alerting`, `operations`; `bot stop` adds `operations`; `status` adds `operations` and `alerting`.
- [x] `bot list` imports none of `binance`, `dateparser`, `aiohttp`, `pyarrow`. Evidence: the same test, `_HEAVY`.
- [x] A command that declares nothing, the host (`run`), the GUI and the interactive shell build every context as before. Evidence: `test_a_command_that_names_no_contexts_still_gets_all_of_them` (`preflight`), `test_a_command_builds_the_bounded_contexts_its_declaration_names` (`sync` and `preflight` get `None`), sanity tier (below).
- [x] Every command's behaviour and output unchanged. Evidence: `status`, `status --json`, `alert test` and `alert test --json` compared byte for byte (timestamps removed) with the master build on an empty data root; the unit and integration tiers (below).
- [ ] (not met) `python -X importtime main.py bot list` shows the pre-log phase at least 2x faster. **Partly met, not claimed**: see the notes. Measured in the CI container at 1.76-1.83x by median wall time (import time alone 1.5-2.0x); the VPS is unmeasured.
- [x] A typo in a `Deferred` path or in a `"modules"` list is caught before the first run on a server. Evidence: `test_every_deferred_literal_resolves.py` (one case per literal), `test_every_declared_module_exists.py`, `select_modules` refuses an unknown name.

## 3. Design
Two cuts for two kinds of cost, each where the cost is caused (`PRO-014` §4). The pattern is lazy initialization through the project's own `Deferred` (CONSTITUTION P5: apply before you invent), selection is a dependency closure over the declared `dependencies`.

- **Which contexts:** `"modules": [...]` on a command or verb in `cli_commands.json`; absent means all (the direction `read_only` also takes). Declared per verb, not per group, so a verb someone adds later gets everything until it says otherwise. `command_needed_modules` reads it; `main._Boot` carries it to `create_app(needed_modules=...)`; `select_modules` returns the entries in list order plus their `dependencies`, because the Engine raises `ExtensionDependencyError` for a missing one and a context reads its suppliers' ports (`bots` resolves `trading`'s venue ports even to list).
- **Which classes:** `ModuleEntry(module_id, class_name)` instead of a class in `MODULES`; it is callable, so `register_modules` instantiates it. The `module_id` is repeated on purpose (it must be known before the import) and a test holds it equal to the class's.
- **Which libraries:** the exchange-SDK adapters (`BinanceWebsocketService`, `MarketDataSessionFactory`, `FuturesSessionFactory`, `BinanceKeyEnvironmentProbe`, `VenueAssembly`) are built through `exchange_adapters.py` in each context; `ParquetWriter` through `parquet_export.py`; the indicator scripts through `shell/indicator_scripts.py`; `InteractiveShell` and the six headless commands through `Deferred` in `main.py`; the writable half of `BotsModule.boot` through `bots/composition/writable_boot.py`.
- **Two mechanisms were corrected, not worked around:** `LiveStreamEngineAdapter` took the stream service in its constructor, so every boot built the websocket service (it now asks the container at `stop()` whether one was built, as `MarketDataModule.shutdown` already did for the client, BUG-122); `TradingModule.shutdown` built every venue's adapters to stop a stream nobody opened (`IVenueContexts.built()`, a non-abstract method whose default keeps the fake and every other implementer complete).
- **`LazyHostControl`** resolves `IHostControl` at the first `send`, so `bot list` needs no `operations` (and so no `alerting`); the control verbs declare `operations`.
- **Rejected:** function-local imports (`PLC0415` debt only falls); an Engine change to tolerate missing dependencies (another repository); registering the suppliers without their bodies (measured to save about 0.1 s more, a redesign of the read side); a resident process (out of scope).

## 3a. Reuse
`Deferred` (`src/core/contracts/deferred.py`, catalog row "Name a widget or factory by import path"): used for every path above. `command_access.py` (catalog row "Decide before the app boots whether a command needs the writable copy"): extended in place with `command_needed_modules`; its `Capability:` block names it. `register_modules` generalised from classes to "anything that makes a module when called". `scripts/render_capability_index.py --write` regenerated. No UI need.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/config/cli_commands.json` | `"modules"` on `bot list/show/export/order` (`bots`), `bot start/stop/pause/resume/edit` (`bots`, `operations`), `status` (`operations`), `alert test` (`alerting`) |
| `src/shell/modules.py`, `module_selection.py` (new), `module_registration.py`, `composition_root.py` | `ModuleEntry`; `select_modules`; `create_app(needed_modules=)`; indicator scripts bound by path |
| `src/main.py`, `src/support/cli_host/command_access.py` | headless commands and shell by `Deferred`; `_Boot`; `command_needed_modules` |
| `src/shell/indicator_scripts.py` (new), `src/support/indicators/indicator_script_registry.py` | the script registry built on first ask; the registry no longer imports the scripts |
| `src/modules/market_data/composition/exchange_adapters.py` (new), `adapter_bindings.py`, `market_data_venues.py`, `adapters/live_stream_adapter.py`, `adapters/binance/klines_type.py` (new), `adapters/binance/client.py`, `application/database/export_market_data/{handler,parquet_export}.py` | SDK and `pyarrow` named by path; the live-stream adapter looks the service up at `stop()`; `klines_type_for` moved out of the venue contract |
| `src/support/binance_gateway/contracts/binance_endpoints.py`, `scripts/epic021a_venue_probe.py` | the contract imports nothing from `python-binance`; the probe imports `klines_type_for` from its new home |
| `src/modules/trading/composition/{exchange_adapters (new),adapter_bindings,venue_contexts}.py`, `contracts/i_venue_contexts.py`, `contracts/testing/contract_venue_contexts.py`, `module.py` | session factory, key probe and `VenueAssembly` by path; `built()` and its contract test; shutdown visits built venues |
| `src/modules/bots/{module.py,composition/writable_boot.py (new),cli/lazy_host_control.py (new),cli/bot_cli_handler.py}`, `application/services/lifecycle/{bot_executors,bot_runner}.py` | the writable boot reached by path; `LazyHostControl`; type-only imports of the Grid executor |
| `scripts/measure_startup.py` (new) | the measurement, runnable on the VPS |
| `tests/...`, `.claude/rules/capabilities.md`, `Docs/...`, `Tasks/proposal/PRO-014.md` | see §5 and §6 |

## 5. Testing
Tiers per `ci-rule.md` §2. New: `tests/unit/shell/test_module_selection.py`, `tests/unit/support/cli_host/test_every_declared_module_exists.py`, `test_command_access.py` (3 cases), `test_main_entry.py` (the declared set reaches `create_app`), `tests/unit/modules/bots/cli/test_lazy_host_control.py`, `tests/unit/modules/trading/test_shutdown_builds_no_venue_nobody_asked_for.py`, the `built()` case in `VenueContextsContract` (real registry and fake), `tests/unit/modules/market_data/adapters/test_live_stream_adapter.py`, `tests/unit/architecture/test_every_deferred_literal_resolves.py`, `tests/unit/scripts/test_measure_startup.py`, and the process test named in §2. Updated, not weakened: the architecture guards that listed `MODULES` as classes or walked static imports (`test_module_declarations`, `test_deferred_targets_resolve`, `test_a_bus_subscriber_is_constructed`, `test_the_shared_composition_path_imports_no_ui_package` now follows `Deferred`/`ModuleEntry` strings and has a mutation case, `test_only_the_venue_assembly_constructs_venue_adapters` counts a `Deferred` path as the construction); `test_klines_type_for_every_market` moved with the function.

Results and mutation runs: see the implementation notes.

## 6. Docs touched
`Docs/OPERATIONS/headless_runbook.md` §2 and §8 (the `compileall` step and why it is the runbook's and not the unit's); `Docs/SDD/04_boot_and_configuration.md` boot step 3; `Docs/MODULES/bots/07-deployment.md` (the writable half of `boot()`); `Docs/LEARNING/002_lazy_composition_a_command_builds_only_what_it_needs.md` and its index; `Tasks/proposal/PRO-014.md`; `.claude/rules/capabilities.md` (generated).

## Implementation notes (written when done)
**Measured** (`scripts/measure_startup.py --against <master build> --runs 25 -- bot list`, empty data root, bytecode compiled, 4-core container, two runs, interleaved):

| Build | wall median | wall min | `-X importtime` top-level |
| :--- | :--- | :--- | :--- |
| master `f1aec4e` | 2.07 s / 2.12 s | 1.78 s / 1.84 s | 1.79 s / 1.54 s |
| this branch | 1.18 s / 1.16 s | 0.94 s / 1.03 s | 0.87 s / 1.14 s |
| ratio | 1.76x / 1.83x | 1.9x / 1.8x | 2.1x / 1.4x |

The container is noisy (a run varies by 30%), so the ratio is a range, not a point. **The 2x was not reached by median wall time.** What is left of a `bot list` is the Engine's floor (`import main` alone is about 0.42 s: its health extension imports the SQL toolkit, ~0.2 s, for every command) plus the registration of `bots`, `trading` and `market_data` (~0.45 s, mostly their contracts and use-case modules). Two further steps, each its own proposal: the Engine's health query should not import persistence at import time (Engine repository, separate confirmation; market_data's SQL adapters would also have to be named by path to benefit), and registering a supplier without its use cases (measured at about 0.1 s). Python's own exit adds 0.15-0.2 s after `main()` returns, outside the pre-log phase.

**Verification**, on the merged tree (master `f1aec4e`): commit tier `ci-local.ps1 -SkipTests` PASS before the merge; unit tier 15745 passed; integration 826 passed, 3 skipped, 1 failed (`test_workbench_conformance[True-1024x700]`, a window-size check that fails the same way on master in this container); sanity tier (`tests/sanity`) 65 passed; `status` and `alert test` outputs identical to master. Mutations run red: shutdown visiting enabled venues, the live-stream adapter stopping unconditionally, a typo in a `Deferred` path, no dependency closure, eager `IHostControl`.
