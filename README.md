# Sagittarius Elite Warrior

Grid trading bots for **Binance Spot and USD-M Futures**, on the testnets and on mainnet. The same application runs two ways:

- a **desktop app** (PySide6), to design, backtest, run and watch bots;
- a **headless host** (`main.py run`), which runs the same bots as a service on a Linux VPS.

It is built on the Sagittarius Engine framework, a separate repository pinned by `engine.ref`.

> [!IMPORTANT]
> **Real money.** Mainnet venues trade real funds. Every mainnet start and resume from the command line needs `--confirm-venue <venue>`. A key that can withdraw is refused. Read [`Docs/OPERATIONS/headless_runbook.md`](Docs/OPERATIONS/headless_runbook.md) §0, "what is not supported yet", before you leave a mainnet bot unattended.

## What it does

| Area | What you get |
| :--- | :--- |
| **Bots** | Grid bots, Long, Short or Neutral on Futures and Long on Spot. A bot waits for the price to enter its range before it places anything. On Futures a protective stop stands on the exchange. Stop loss and take profit. Restart recovery: after a restart a bot is RECOVERING until a person resumes it. Order pacing within the owner's caps: 150 open orders, 60 orders a minute, 250 ms apart. |
| **Strategies** | Indicator strategies (EMA, RSI, MACD, …), shared by backtest and live, armed on a symbol from the Bots menu. |
| **Backtesting** | Grid and strategy replay with fees, funding and liquidation, the same entry rule as live, and out-of-sample validation. |
| **Trading** | Manual Spot and Futures orders, an account desk, an Emergency Stop, and request-weight budgeting against Binance's limits. |
| **Market data** | History synced to SQLite and live WebSocket streams. |
| **Alerting** | Discord and Telegram. A bot halt, stop loss, take profit or a lost stream is CRITICAL or WARNING. A six-hourly heartbeat, a daily summary, quiet hours, and a dead man's switch for a host that goes silent. |
| **Operations** | `sew-install`, `sew-update`, `sew-key` and `sew-backup` scripts for a VPS. A pre-flight check at every start. A daily loss cap across all bots. Control of each bot on the running host. |

## Architecture, in one screen

The code is split into **bounded-context modules** under `src/modules/`: `market_data`, `trading`, `bots`, `strategy`, `backtesting`, `alerting` and `operations`. Each module is layered **domain → application → adapters/UI**, and dependencies point inwards. Modules talk through explicit contracts (`contracts/`, ABCs) and events on the engine's event bus, never through each other's internals. `src/support/` holds shared technical code, such as the Binance gateway and the log view. `src/shell/` and `src/presentation/` compose the desktop app and the CLI.

- Rules: [`.claude/rules/architecture-rule.md`](.claude/rules/architecture-rule.md) · reuse catalogue: [`.claude/rules/capabilities.md`](.claude/rules/capabilities.md)
- Design per module: [`Docs/MODULES/`](Docs/MODULES/) · use cases: [`Docs/SPEC/`](Docs/SPEC/README.md) · which document answers what: [`Docs/README.md`](Docs/README.md)

## Run it on a desktop (Windows)

```powershell
.\scripts\run.ps1            # creates .venv, installs the requirements and the pinned engine, opens the app
.\scripts\run.ps1 -CLI       # the same setup, then the interactive command line
```

Code imports by absolute package path (`Sagittarius_Elite_Warrior.src…`), so the folder must keep the name `Sagittarius_Elite_Warrior`, and `PYTHONPATH` is its parent. `run.ps1` sets both.

Add your Binance keys in **Options → Trading**:
- A mainnet key goes to the operating system's keyring.
- A testnet key goes to `src/config/secrets.local.json`, which is not tracked.
- The key's IP whitelist on Binance must hold your **public** IP. **Show public IP** on that page tells you what it is.

## Install and run on a VPS (Ubuntu, systemd ≥ 251)

The full procedure, with every check, is [`Docs/OPERATIONS/headless_runbook.md`](Docs/OPERATIONS/headless_runbook.md). In short:

```bash
# 1. Install, once: creates the `sew` account, /opt/sew, the venv, the systemd unit and the helper scripts
git clone https://github.com/anhembedded/Sagittarius_Elite_Warrior.git
sudo Sagittarius_Elite_Warrior/deploy/linux/sew-install --dry-run   # what it would do
sudo Sagittarius_Elite_Warrior/deploy/linux/sew-install

# 2. Keys: checked against Binance before they are written; a key that can withdraw is refused
sudo sew-key add                      # paste key and secret (not echoed), then type the venue to confirm
sudo sew-key list

# 3. Start the host and read its pre-flight
sudo systemctl enable --now sew-run
journalctl -u sew-run -o cat --since "5 minutes ago" | grep '\[preflight\]'

# 4. Add a bot designed on the desktop (Bots → Export plan…), with no restart
scp plan.json root@<vps>:/tmp/plan.json           # from your machine
M bot add /tmp/plan.json                          # lands DRAFT, places nothing
M bot start <id> --confirm-venue futures_mainnet  # --confirm-venue only for a mainnet venue

# Day to day
M bot list                                        # every bot, its state and its earnings
M bot show <id>                                   # the plan, the ladder, the risk
M status                                          # the host: bots, feeds, stream, loss cap
sudo sew-update                                   # upgrade: stop, back up, update, start
M bot resume <id> [--confirm-venue <venue>]       # after any restart, each bot is RECOVERING until resumed
```

`M` is a shell helper the install writes to `/etc/profile.d/sew.sh`. It runs `main.py` as the `sew` account. Before real money, also:
- store a Discord webhook (runbook §3);
- store a dead man's switch URL (§3b);
- set `bots.account_loss_cap` (§6);
- put the futures account in Single-Asset mode with USDT margin;
- run each mainnet symbol on **one** host only.

The exit codes are in [`Docs/OPERATIONS/exit_codes.md`](Docs/OPERATIONS/exit_codes.md) and the log is described in [`Docs/OPERATIONS/LOGGING.md`](Docs/OPERATIONS/LOGGING.md).

## Develop

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -c requirements.lock
python scripts/engine_pin.py install
```

- **Every commit:** `pwsh -NoProfile -File scripts/ci-local.ps1 -SkipTests` (ruff, format, mypy, reference check), the architecture tests and the tests you touched.
- **Full gate:** GitHub Actions runs `ci-local.ps1 -Full` on every pull request. It is the authority, and its job log is read, not its badge ([`.claude/rules/ci-rule.md`](.claude/rules/ci-rule.md)).
- **Tests** come in four tiers: `tests/unit`, `tests/integration`, `tests/sanity` and the opt-in desktop end-to-end tests ([`.claude/rules/testing-rule.md`](.claude/rules/testing-rule.md)).
- **Process:** start at [`CLAUDE.md`](CLAUDE.md) and [`.claude/ONBOARDING.md`](.claude/ONBOARDING.md). Every change reaches `master-warrior` through a pull request, and the owner merges code.

## Where things stand

- `python3 scripts/render_board.py`: the task and bug board.
- [`Tasks/ROADMAP.md`](Tasks/ROADMAP.md): the direction.
- [`Tasks/epics/README.md`](Tasks/epics/README.md): the epics.
- [`Tasks/COORDINATION.md`](Tasks/COORDINATION.md): the owner's standing decisions and the streams in flight.
