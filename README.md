# Sagittarius Elite Warrior

Trading bot for **Binance USD-M Futures**, consisting of a **PySide6 desktop application** and a **headless CLI**, built on the [Sagittarius Engine](https://github.com/anhembedded/Sagittarius_Engine) framework following **Clean Architecture** (Domain → Application → Infrastructure/Presentation).

> [!IMPORTANT]
> **Capital Safety Guardrail:** The bot **only** places orders on **Binance USD-M Futures Testnet**. The path for real-money order routing **does not exist in the code** — the [`TradingVenue`](src/support/binance_gateway/contracts/trading_venue.py) value object intentionally **lacks a `MAINNET` member**: enabling real trading is an epic that requires adding that member and passing code review, not a configuration flag anyone can flip.

| | |
| :--- | :--- |
| **Python** | ≥ 3.12 (enforced by `tests/sanity/test_python_floor.py` — see [`install-rule.md`](.claude/rules/install-rule.md) §1b) |
| **UI** | PySide6 (QtWidgets) + pyqtgraph for charts; **no QML for new code** (ADR D20, 2026-09-13) — legacy QML is being removed by `EPIC-025`, with a guard blocking new `.qml` files |
| **Storage** | SQLite (WAL) via SQLAlchemy |
| **Mandatory Verification Gate** | [`scripts/ci-local.ps1 -Full`](scripts/ci-local.ps1) + [GitHub Actions](.github/workflows/ci.yml) |
| **Status / Roadmap** | [`Tasks/ROADMAP.md`](Tasks/ROADMAP.md) · [`Tasks/epics/README.md`](Tasks/epics/README.md) · [Bug Board](Tasks/bug_report/README.md) |

---

## 1. What the Bot Can Do Today

| Capability | Description |
| :--- | :--- |
| **Historical Data Sync** | Downloads OHLCV candles from Binance to SQLite (WAL mode, sharded by symbol/timeframe), saving UTC-standard timestamps. |
| **Realtime Market Stream** | Async Websocket, broadcasting `MarketTickEvent` to the Event Bus for charts and strategies. |
| **Indicator & Strategy Engine** | EMA/WMA/RSI/MACD/Support-Resistance; strategies shared across backtest and live trading (`src/domain/strategies/`), parameters declared via parameter schema instead of being hardcoded. |
| **Backtesting** | `PaperExchange` simulating futures order execution (SHORT + leverage), fees, exit reasons, equity curves, metrics suite, and **out-of-sample** split for strategy validation. |
| **Desktop Application** | 5 screens: Dashboard/Dev Board, Backtest, Data Management, **Trading**, Settings — sharing `PageShell` (header / context bar / workspace + rail / console). |
| **Futures Testnet Trading** | Connection testing, order normalization per exchange filters (step/tick/minNotional), dry-run via `POST /fapi/v1/order/test`, real order placement on testnet, User Data Stream connected to `OrderFeed`; environment banner displayed on all screens (via `PageShell`), **Emergency Stop** on the Trading screen. |
| **Live Strategy on Trading Screen** | Select strategy + Strategy Parameters at runtime, rendering indicators/trend zones of that strategy on the live chart; trading **cannot be enabled** without a loaded strategy. |

**Intentionally not implemented:** real-money trading (mainnet); continuous trading daemon — `trade-once` runs exactly **one** evaluation cycle and exits.

---

## 2. Architecture

Four layers, with dependencies always pointing inwards. Details and rationale for each decision can be found in [`.claude/rules/architecture-rule.md`](.claude/rules/architecture-rule.md) and [`Docs/Diagrams/architecture.md`](Docs/Diagrams/architecture.md).

```text
Presentation  (PySide6 UI, CLI)          ─┐
Infrastructure (Binance, SQLAlchemy,      │  adapter — framework-aware
                engine adapters)          │
Application   (use case CQRS, port)      ─┤  contracts — framework-agnostic
Domain        (entity, indicator,        ─┘  pure Python
               strategy, backtest)
```

Three constraints govern most of the code organization:

1. **Shared Kernel limited to exactly 2 symbols.** `src/domain/` and `src/application/` are only allowed to import `IDomainEvent` and `BaseEvent` from the engine; everything else must go through a **port** in `src/application/ports/` with an adapter in `src/infrastructure/engine_adapters/`. A test strictly locks this allow-list.
2. **Explicit contracts** — implicit duck-typing is forbidden. `abc.ABC` is the default; `typing.Protocol` is used only when inheritance is impossible (`QObject` class, existing base class, third-party class) and docstrings must state the rationale.
3. **Separation by abstraction level.** Components at different abstraction levels cannot share files or directories; files > 400 lines or classes > 15 public methods must be split.

**Two independent repositories, not submodules.** `Sagittarius_Engine` (framework) and `Sagittarius_Elite_Warrior` (this app) have separate remotes, rule trees (`.claude/`), and task boards — commits and pushes are kept distinct, with no pointer "bumping" step.

---

## 3. Directory Structure

```text
Sagittarius_Elite_Warrior/
├── src/
│   ├── domain/              # Pure Python: entity, value object, indicator, strategy,
│   │                        # backtesting (PaperExchange, metrics, out-of-sample), trading
│   ├── application/         # Use case (CQRS: command/query/handler), port, service,
│   │                        # event handler — framework-agnostic
│   ├── infrastructure/      # Adapter: binance/, persistence/ (SQLAlchemy), credentials/,
│   │                        # engine_adapters/
│   ├── presentation/
│   │   ├── cli/             # JSON-configured parser, interactive shell, headless commands
│   │   └── ui/              # PySide6: app_bootstrapper, main_window, screens/, components/,
│   │                        # kit/ (shared widgets), registry/, state/
│   ├── config/              # app_config.json, user_config.json, cli_commands.json
│   └── main.py              # CLI entry point (headless + interactive shell)
├── tests/                   # unit/ · integration/ · sanity/ · testnet/ (opt-in)
├── scripts/                 # ci-local.ps1, run.ps1, run-ui.ps1, preview-qml.ps1, probe/benchmark
├── Tasks/                   # ROADMAP.md, epics/, bug_report/, backlog/, completed/, reports/
├── Docs/                    # Architecture diagrams, project intent, detailed design
├── .claude/                 # ONBOARDING.md, rules/, skills/, agents/, templates/ — workflow for human & AI agents
└── database/                # trading.db (uncommitted)
```

---

## 4. Installation

**Important note on `PYTHONPATH`:** Code imports using absolute package paths (`Sagittarius_Elite_Warrior.src...`), so `PYTHONPATH` must point to the **parent directory** containing this repository, and the repo folder name must be `Sagittarius_Elite_Warrior` (using underscores).

### Windows (PowerShell) — Automated Environment Scripts

```powershell
.\scripts\run.ps1        # creates .venv, installs dependencies + engine, runs CLI
.\scripts\run-ui.ps1     # same as above, but launches the desktop app
```

### Manual Setup (Linux/macOS/Windows)

```bash
python3.12 -m venv .venv
source .venv/bin/activate                 # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install git+https://github.com/anhembedded/Sagittarius_Engine.git
```

When developing/debugging the engine alongside the app, install the local version instead of GitHub:

```bash
pip install -e ../Sagittarius_Engine        # run from parent workspace directory
```

Linux additionally requires `pwsh` to run the **mandatory verification gate**, and several system libraries for Qt running `offscreen` (`libegl1`, `libgl1`, `libxkbcommon0`, `libfontconfig1`, `libdbus-1-3` on a clean container — let `ImportError` identify missing `.so` files). Full instructions: [`.claude/rules/install-rule.md`](.claude/rules/install-rule.md) §2b, §3.

### Futures Testnet API Key Configuration

Precedence order: **environment variables first, file second** — environment variables always take precedence, allowing headless execution (CI/VPS) without writing secrets to disk.

```bash
export BINANCE_FUTURES_TESTNET_API_KEY=...
export BINANCE_FUTURES_TESTNET_API_SECRET=...
```

If environment variables are not set, the app reads `src/config/secrets.local.json` (which is in `.gitignore`; the Settings screen writes to this exact file). Variable names are strictly bound to the **venue** rather than generic names — key mix-ups across environments are precisely what this guardrail was designed to prevent.

---

## 5. Running the Application

### 5.1 Desktop Application (PySide6)

```powershell
.\scripts\run-ui.ps1                 # normal execution
.\scripts\run-ui.ps1 -Dev            # DEBUG logging -> logs/dev-<timestamp>.log, enables FPS/click logging
.\scripts\run-ui.ps1 -Debug          # TRACE logging -> logs/debug-<timestamp>.log (includes -Dev)
```

Manual equivalent (run from parent workspace directory):

```bash
PYTHONPATH=. python -m Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper
```

The `--self-check` flag boots the actual app, runs the event loop for exactly one cycle, and exits with a real exit code — used to verify that the app genuinely starts and **genuinely exits**, rather than just inside a pytest process.

### 5.2 CLI

Without arguments → **interactive shell** (`cmd`-based, type `help` to list commands, currently routing `sync`, `stream`, `exchange-status`). With arguments → executes the command directly and exits, suitable for cron/VPS.

```bash
PYTHONPATH=. python Sagittarius_Elite_Warrior/src/main.py            # interactive
PYTHONPATH=. python Sagittarius_Elite_Warrior/src/main.py <command> ... # headless
```

| Command | Description |
| :--- | :--- |
| `sync --symbols BTCUSDT,ETHUSDT --interval 1m --days 30` | Syncs historical candles to SQLite. |
| `stream start --symbols BTCUSDT --interval 1m` / `stream stop` | Enables/disables realtime websocket stream. |
| `exchange-status` | Checks Futures Testnet connectivity: signature, clock skew, balance, position mode. |
| `order-preview --symbol BTCUSDT --side BUY --qty 0.0137 --price 60000 [--json]` | Normalizes order according to exchange filters (step/tick rounding, `minNotional` check) — **does not send anything anywhere**. |
| `order-dry-run --symbol ... --side ... --qty ... --price ...` | Sends to `POST /fapi/v1/order/test`: exchange validates signature/permissions/payload, **creates no order**. |
| `trade-once --symbol BTCUSDT --interval 1m --strategy <key> [--live]` | Runs **one** strategy evaluation cycle through the complete safety pipeline. Defaults to dry-run; `--live` actually places the order (on testnet). |

Command list and parameters are generated from [`src/config/cli_commands.json`](src/config/cli_commands.json) — adding a command involves editing the config file plus adding a handler, not modifying the parser.

### 5.3 Previewing a UI Screen Without Booting the App

```powershell
.\scripts\preview-qml.ps1 --list
.\scripts\preview-qml.ps1 <screen-name>
```

Every UI package must include a `preview.py` declaring `build_preview() -> QWidget`; a test strictly enforces this.

---

## 6. Testing & CI

### Mandatory Gate

```powershell
cd Sagittarius_Elite_Warrior
.\scripts\ci-local.ps1 -Full          # Linux: pwsh -NoProfile -File scripts/ci-local.ps1 -Full
```

`-Full` executes: `ruff check` + `ruff format --check` (with added rulesets `S`/`PLR2004`/`B`/`SIM`/`ERA`/`N` — Bandit-style security/quality checks), `mypy` on `src` **and** `scripts` **in a single command**, `.claude/` reference guard, all tests, Sanity tier running sequentially, and an 80% coverage threshold. The `-UnitOnly`/`-SanityOnly`/`-SkipLint`/`-SkipTests` flags are **diagnostic tools**, not workarounds for a red gate.

> [!WARNING]
> **Do not read console output — read log files.** In offscreen mode, Qt outputs harmless errors to stderr **after** pytest's summary line, so `| tail` displays noise and may **hide** actual failures. Always use `> logfile 2>&1`, then `grep` that file for `FAILED|ERROR|Traceback|ResourceWarning`. Two real bugs (`BUG-029`/`BUG-030`) were exposed only because full log files were inspected.

### Four Testing Tiers

| Tier | Purpose / Scope |
| :--- | :--- |
| **Unit** (`tests/unit/`) | Pure functions, data contracts, invariants, deterministic component behavior. |
| **Integration** (`tests/integration/`) | Real user/application flows across real collaborators, with external boundaries seeded/faked locally. |
| **Sanity** (`tests/sanity/`) | Real app boot, real DI wiring, **and silent execution** — `diagnostic_guard` fails on any Qt message, log ≥ WARNING, or `warnings.warn`. Adding a new screen does **not** require adding a test here. |
| **Desktop E2E** | Real flow on a real graphic session (non-offscreen), real Qt inputs — opt-in, required for rendering changes or reported GUI bugs. |

`tests/testnet/` is **not** a fifth tier: it touches the live exchange using real credentials, blocked by **two layers** (`-Full` always passes `--ignore`, and the tier itself gates via `SEW_TESTNET_TESTS=1` + resolved credentials):

```powershell
$env:SEW_TESTNET_TESTS = "1"
.\scripts\ci-local.ps1 -TestnetOnly
```

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push/PR to `master-warrior`. These two gates are **not duplicates of each other** (parallel vs sequential, Sanity job isolation) — do not assume either subsumes the other.

---

## 7. Data

All downloaded candles reside in `database/trading.db` (SQLite, WAL mode; directory configured via `database.dir` key, uncommitted). Quick view with VS Code **SQLite Viewer** extension: right-click `.db` file → *Open to the Side*, open table `klines`.

The **Data Management** screen in the app offers additional capabilities: scanning existing data by symbol/timeframe and detecting **gaps** before backtesting or enabling live streams.

---

## 8. Contributing — Read Before Writing Code

This repository has mandatory workflows applying to both humans and AI agents. Single entry point: **[`.claude/ONBOARDING.md`](.claude/ONBOARDING.md)** — 2-repo structure, task/bug lifecycle, real Linux verification commands, `ROADMAP.md` bookkeeping, and §8 listing traps that have **actually produced broken code** here.

| Task / Topic | Reference Document |
| :--- | :--- |
| Decision authority vs asking | [`ONBOARDING.md`](.claude/ONBOARDING.md) §7 |
| Architecture: layers, Port/ABC, Shared Kernel, event placement | [`architecture-rule.md`](.claude/rules/architecture-rule.md) |
| Code quality: typing, magic number, cohesion, lazy import | [`code-quality-rule.md`](.claude/rules/code-quality-rule.md) |
| Before declaring "done" | [`ci-rule.md`](.claude/rules/ci-rule.md) |
| Before each commit | [`commit-rule.md`](.claude/rules/commit-rule.md) |
| When a bug is reported (**mandatory**) | [`fix-bug-rule.md`](.claude/rules/fix-bug-rule.md) |
| Adding/modifying logs | [`logging-rule.md`](.claude/rules/logging-rule.md) |
| Writing tests | [`testing-rule.md`](.claude/rules/testing-rule.md) |
| UI development: screen layouts, `preview.py`, icons, table columns | [`ui-presentation-rule.md`](.claude/rules/ui-presentation-rule.md) |
| Any UI code (QtWidgets only, no QML per ADR D20) | [`ui-presentation-rule.md`](.claude/rules/ui-presentation-rule.md) |
| UI background tasks: action ownership, cancellation, Coordinator separation | [`async-ui-action-rule.md`](.claude/rules/async-ui-action-rule.md) |
| Modifying `src/modules/*/domain/**` or `src/modules/*/application/**`: domain truth | [`domain-truth-rule.md`](.claude/rules/domain-truth-rule.md) |
| Environment setup, missing tools | [`install-rule.md`](.claude/rules/install-rule.md) |

Four things that can waste half a day if done wrong:

1. **Never `git push` unless explicitly requested by the user.** `commit` defaults to ask-first; `push` defaults to forbidden. Each repository requires separate confirmation.
2. **Read log files, do not trust console output** (see warning in §6).
3. **Two independent repositories**, not submodules — separate commits/pushes.
4. **Work is often left uncommitted between sessions.** An untouched task board **plus** a dirty working tree means work has **already been done**, just not recorded. Run `git status` in **both** repos and check diffs before drawing conclusions.

### Language

Documentation in `.claude/`, `Docs/`, and `Tasks/` (tasks, bug reports, boards — all `.md` files since 2026-09-12, `ONBOARDING.md` §10; legacy docs kept as-is), code, identifiers, docstrings, comments, commit subjects, UI display strings, and logs: **English**. User conversations: **Vietnamese**.

---

## 9. Status & Roadmap

Numbers (task count, test count, bug count) **constantly shift** — do not trust numbers written in static documentation; refer directly to the source of truth:

| Question | Source |
| :--- | :--- |
| Active epics and progress | [`Tasks/epics/README.md`](Tasks/epics/README.md) |
| Open bugs | [`Tasks/bug_report/README.md`](Tasks/bug_report/README.md) |
| Overall task board | [`Tasks/ROADMAP.md`](Tasks/ROADMAP.md) |
| What recently happened and why | `git log` (commit bodies in this repo include rationale) |
| What is currently in progress | `git status` + diff, in **both** repos |

Full product intent and user stories: [`Docs/PROJECT_INTENT_AND_USER_STORIES.md`](Docs/PROJECT_INTENT_AND_USER_STORIES.md).
