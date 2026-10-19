Status: Current

# Headless runbook: install, run, stop, upgrade and diagnose on a server

`EPIC-038H`. For a person who has a fresh Linux VPS (systemd) or a Windows server and wants the app to run the bots there with no window, as a service. Journey: [`SPEC-015`](../SPEC/SPEC-015_run_the_bots_headless.md) · exit codes: [`exit_codes.md`](exit_codes.md) · logs and the health line: [`LOGGING.md`](LOGGING.md).

## 0. Read this first: what is not supported yet

**This host is not supported for unattended money.** A bot that halts, errs, whose stop gives up, hits its stop loss or take profit, or leaves its range, and every order that fills whole (a silent message, with the cycle's profit on the fill that closes a cycle; `BOT-189`), reaches your Discord channel once you store a webhook (§3, [`EPIC-036G`](../../Tasks/epics/EPIC-036_alerting_module/completed/EPIC-036G_walking_skeleton_halt_to_discord.md)). Until both of these have merged, the rest reaches nobody:

| Missing | What it leaves you without | Task |
| :--- | :--- | :--- |
| The other alert sources | a lost user-data stream or a revoked key is not sent to any channel | [`EPIC-036B`](../../Tasks/epics/EPIC-036_alerting_module/incomplete/EPIC-036B_alert_sources.md) |
| Dead man's switch | nothing tells you the host stopped on its own, or that the machine is off | [`EPIC-036E`](../../Tasks/epics/EPIC-036_alerting_module/incomplete/EPIC-036E_heartbeat_dead_mans_switch_and_summary.md) |

Until then, use the host on a **testnet** venue. The host says whether a channel is configured: with no webhook stored, every start writes the WARNING `no alert channel is configured for bot events; nothing will tell you if a bot halts`, and `--resume-recovering` refuses without `--i-accept-silent-failures`. With a webhook stored, the start says `an alert channel carries bot events` instead.

Also true today, whatever the alerts:

- **Stopping leaves resting orders on the exchange** (decision O1) and nothing watches a stop loss or take profit while the host is down, for a stop, a crash or an upgrade.
- **A bot a restart left RECOVERING stays so until a person resumes it** (decision O2). The person does it from a second shell with `bot resume <id>` (§6, "Control one bot on the running host"), from the Bots tab, or by restarting with `--resume-recovering`.
- The Windows steps and the checklist in §11 have **not been run on a machine** by their author. The Linux unit is checked mechanically (§12) but not yet run under a real systemd.

## 1. Layout this runbook assumes

| Thing | Linux | Windows |
| :--- | :--- | :--- |
| Checkout (the directory must be named `Sagittarius_Elite_Warrior`) | `/opt/sew/Sagittarius_Elite_Warrior` | `C:\sew\Sagittarius_Elite_Warrior` |
| Virtual environment | `/opt/sew/venv` | `C:\sew\venv` |
| Data root (`SEW_DATA_ROOT`: `state/`, `logs/`, the bots' files) | `/var/lib/sew` | `C:\ProgramData\sew` |
| Service account | `sew` (no login) | `NT SERVICE\sew-run` |
| Service | `sew-run.service` | `sew-run` |
| Secrets | `/etc/sew/` | the data root's `secrets\` |

The data root is outside the checkout so an update of the code never touches the bots, and the checkout can be read-only to the service.

## 2. Install on Linux

Needs systemd 247 or newer (`LoadCredential=` arrived in 247), Python 3.12 or newer (the floor; `preflight` checks it), `git`, and outbound HTTPS to the exchange. **No Qt and no display are needed**: the headless requirements install none of Qt's system libraries.

```bash
sudo useradd --system --home-dir /var/lib/sew --shell /usr/sbin/nologin --user-group sew
sudo install -d -o root -g root -m 0755 /opt/sew
sudo install -d -o sew -g sew -m 0700 /var/lib/sew
sudo install -d -o root -g sew -m 0750 /etc/sew /etc/sew/credentials

sudo git clone https://github.com/anhembedded/Sagittarius_Elite_Warrior.git /opt/sew/Sagittarius_Elite_Warrior
sudo python3.12 -m venv /opt/sew/venv
sudo /opt/sew/venv/bin/pip install -r /opt/sew/Sagittarius_Elite_Warrior/requirements-headless.txt \
    -c /opt/sew/Sagittarius_Elite_Warrior/requirements.lock
sudo /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/scripts/engine_pin.py install
sudo /opt/sew/venv/bin/python -m compileall -q /opt/sew/Sagittarius_Elite_Warrior   # see "Compile the checkout" below

sudo cp /opt/sew/Sagittarius_Elite_Warrior/deploy/linux/sew-run.service /etc/systemd/system/
sudo systemctl daemon-reload
```

**Compile the checkout, once after the clone and again after every `git pull` or `git checkout`** (`PRO-014`). The `sew` account cannot write into the checkout, so Python cannot keep the bytecode of the code it imports, and without it every command, `bot list` and `status` included, compiles the application's thousands of files again. Measured on the first VPS (2026-10-17): `bot list` took 3.66 s with the checkout uncompiled and 3.03 s after `compileall` as root, so skipping the step costs about 0.6 s on every command. Run it as root, which can write the `__pycache__` directories, with the service's own interpreter (the bytecode is valid for one Python minor version). It writes only `__pycache__` directories. Nothing else is needed: `PYTHONDONTWRITEBYTECODE=1` in the unit is deliberate and stays, so the host never tries to write there.

*Why the runbook and not the unit or a script.* `scripts/render_service_files.py` renders the unit from the host's constants, and `ExecStartPre=+` could run the command as root before each start, but that is wrong for two reasons: it would run outside the sandbox the unit exists to enforce (`ProtectSystem=strict`, `NoNewPrivileges`) and add seconds to every restart, and it would not help the commands an operator types between restarts, which are the ones that pay. There is no install script on Linux: this section is the install. The step therefore sits where the code changes, here and in step 4 of §8.

The unit is [`deploy/linux/sew-run.service`](../../deploy/linux/sew-run.service). It is **generated** from the host's own constants by `python3 scripts/render_service_files.py --write`; do not edit the copy in the repository, a guard compares it with the generator. To change a setting on one server use a drop-in (`sudo systemctl edit sew-run`), not an edit of the file. What it does:

- `Restart=on-failure`, `RestartSec=10`, `StartLimitIntervalSec=0`: restart after any failure, ten seconds apart, forever.
- `RestartPreventExitStatus=2 3 4 5`: **never** restart on a usage refusal (2), a held lock (3), a failed pre-flight (4) or a fault only the operator can fix (5: no key, a rejected key, a key that can withdraw). A restart would only repeat it, and repeating a rejected key is how an IP gets banned. The numbers come from the exit-code table; see [`exit_codes.md`](exit_codes.md). Exit `1` (a crash) and `6` (the exchange is out of reach) are restarted.
- `TimeoutStopSec=62`: above the longest stop. The formula is written in the unit: `ceil(--stop-timeout + 30 s + 2 s) + 5 s = ceil(25 + 30 + 2) + 5`. The host leaves by itself after 57 s at the latest, so systemd's `SIGKILL` never has to.
- `Type=notify` with `--host-signal sdnotify`: the unit is "active" only once the pre-flight passed and the bots were restored, so a start that dies in the pre-flight is a failed start. (The notify socket does not exist in a container: §13.)
- `MemoryMax=1G`, a dedicated no-login account, `ProtectSystem=strict` with the data root opened by `StateDirectory=`, `NoNewPrivileges` and the other lines you can read in the file. The host writes its data root and nothing else.
- No `log.file`, no `--dev`, no `--debug`: the log is standard output, which the journal captures and bounds ([`LOGGING.md`](LOGGING.md) §1).

## 3. Provision the keys

A key must be **bound to the server's address** at the exchange, must **not** be allowed to withdraw (the pre-flight refuses a key that can), and must never appear in a unit file, a plan file, a log or a shell history.

**Testnet** (the first run): the environment is the source. Put the four names in a file only root and the service can read:

```bash
sudo install -m 0640 -o root -g sew /dev/null /etc/sew/sew.env
sudoedit /etc/sew/sew.env
```

```text
BINANCE_FUTURES_TESTNET_API_KEY=<your futures testnet key>
BINANCE_FUTURES_TESTNET_API_SECRET=<your futures testnet secret>
BINANCE_SPOT_TESTNET_API_KEY=<your spot testnet key>
BINANCE_SPOT_TESTNET_API_SECRET=<your spot testnet secret>
```

A venue you do not use can be left out. The unit reads this file if it exists (`EnvironmentFile=-`).

**The unit loads the four mainnet credential files and the Discord webhook's file even on a testnet-only server.** Its `LoadCredential=` lines name them, and systemd refuses to start the service when one is missing, with `status=243/CREDENTIALS` ("Failed to set up credentials"). This was observed on the first VPS install, on 2026-10-14 (systemd 255). A testnet-only server does one of two things:

- **Create the five files empty**, the same command as for mainnet below (and fill in the webhook, below, to get alerts). An empty credential reads as "no key". Use this when the server will later go to mainnet, because nothing changes then except filling the files in.
- **Clear the list with a drop-in.** A `LoadCredential=` line with no value resets the unit's list, so the service starts without the files. Put it in the same drop-in as `--start-planned` (§8), and remove it before any mainnet venue.

**Mainnet**: systemd credentials (decision O3). Each secret is a file only root can read; the unit hands it to the service through `LoadCredential=`, so it is not in the service's environment and not inherited by a child process. The unit names four files; create all four, **empty for a venue you do not use** (an empty credential reads as "no key"; a missing file would stop the unit from starting):

```bash
for name in futures_mainnet_api_key futures_mainnet_api_secret spot_mainnet_api_key spot_mainnet_api_secret alerting_discord_webhook; do
  sudo install -m 0600 -o root -g root /dev/null "/etc/sew/credentials/$name"
done
# For a venue you use, type the value without echoing it. `read -s` is bash (the shell you
# are logged in to; dash, which is `sh` on Debian and Ubuntu, has no `read -s`), and `printf` is
# a builtin, so the value is in no process's argument list and not in your history:
read -rsp "futures mainnet key: " v; echo
printf '%s' "$v" | sudo tee /etc/sew/credentials/futures_mainnet_api_key > /dev/null; unset v
```

Mainnet bots are never started by the host without you typing the venue (`--confirm-venue`, decision O8); the unit passes none.

**Upgrading an existing install** to a version whose unit names `alerting_discord_webhook`: create that file (empty is fine) **before** you install the regenerated unit and restart, or systemd refuses to start the service with `status=243/CREDENTIALS`:

```bash
sudo install -m 0600 -o root -g root /dev/null /etc/sew/credentials/alerting_discord_webhook
```

**Alerts to Discord** (`EPIC-036G`, decision D3 of the [2026-10-15 alerting record](../../Tasks/epics/EPIC-036_alerting_module/DECISION_2026-10-15_walking_skeleton_and_headless_secrets.md)). The webhook is a secret like a key: whoever holds its URL can post to your channel. It is the systemd credential `alerting_discord_webhook`, read only by the service, never in an environment variable, a config file or a log line. In Discord: the channel's **Edit Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL** (a channel only you read is best). Then write it to its file and restart the service (`sudo systemctl restart sew-run`):

```bash
sudo install -m 0600 -o root -g root /dev/null /etc/sew/credentials/alerting_discord_webhook
# Paste the URL without echoing it, as for a key above.
read -rsp "Discord webhook URL: " v; echo
printf '%s' "$v" | sudo tee /etc/sew/credentials/alerting_discord_webhook > /dev/null; unset v
```

An empty file means no Discord channel, and the host warns at start as in §0. A value that is not a Discord webhook URL (`https://discord.com/api/webhooks/<id>/<token>`) is refused the same way, with the WARNING `[alert-channel] discord is off: the Discord webhook credential (alerting_discord_webhook) does not hold a Discord webhook URL`, which never quotes the value. **To rotate the webhook** (it leaked, or you deleted it in Discord): create a new one, run the block above again, and restart: systemd copies a credential when the service starts, so the running host keeps the old one until then. On Windows the webhook is a file named `alerting_discord_webhook` in the `SEW_SECRET_FILES_DIR` directory (§9), like the keys.

## 4. Run the pre-flight

For **testnet**, as the service account with the keys in the environment (the service is not running, so the data root is free):

```bash
sudo -u sew bash -c 'set -a; . /etc/sew/sew.env; set +a; \
  PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew \
  /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py preflight --venue futures_testnet'
echo "exit $?"
```

For **mainnet** the credentials exist only inside the unit, so the pre-flight is the one `run` itself performs before it restores any bot: `sudo systemctl start sew-run`, then read its lines (`journalctl -u sew-run -o cat | grep '\[preflight\]'`). A failed check stops the start with exit 4, 5 or 6 and an ERROR line per finding with its remedy.

Exit codes of `preflight`: `0` nothing failed (a WARN passes), `4` a check failed, `5` credentials absent or refused, `6` the exchange is unreachable. What to do on each check:

| Check | A FAIL or WARN means | Do |
| :--- | :--- | :--- |
| `python-floor` | the interpreter is below 3.12 | install Python 3.12+ and rebuild `/opt/sew/venv` |
| `data-root-writable` | the service account cannot write the data root | `sudo chown -R sew:sew /var/lib/sew`; check it is not a read-only mount |
| `disk-space` | WARN below 1 GiB or 10 % free, FAIL below 100 MiB | free space; a full disk stops the database write, not the network call, so the symptoms are strange |
| `clock-skew` | WARN above 500 ms, FAIL at 1000 ms against the exchange's time | `timedatectl status`; enable `systemd-timesyncd` or `chrony`; the exchange refuses a request stamped 1000 ms ahead (`-1021`) |
| `credentials-present` | no key for a venue in use (exit 5) | §3; the line names which source answered, never the value |
| `key-permissions` | the exchange rejected the key (`-2015`: key, address or permission) or the signature (`-1022`) | check the key's IP binding includes this server, and that its secret is the right one |
| `no-withdraw-permission` | the key can withdraw | create a new key without withdrawal; never run with this one |
| `outbound-address` | the address the exchange sees is not the one the key is bound to, or could not be read | bind the key to the address shown, or fix the route |
| `bot-files-readable` | WARN: a bot file in `state/bots/` was written by a newer build, or is damaged; its bot is **not loaded** and the file is left untouched | §8: roll back to the build that wrote it, or copy the file out if it is damaged; do not edit it |

`--skip <ids>` skips checks; `run --skip-preflight` skips them all and logs a WARNING. Neither belongs in the unit.

## 5. First run, on the testnet

```bash
sudo systemctl enable --now sew-run
systemctl status sew-run --no-pager
journalctl -u sew-run -o cat -f
```

Expected, in order: `[run]` (the options in effect), `[preflight]`, `[host] BOOTING -> SERVING`, the one `[alerts]` WARNING from §0, then a `[health]` line every 60 seconds. Look at it from a second process:

```bash
sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew \
  /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py status
echo "exit $?"
```

`status` opens no connection and takes no lock: it reads `state/health.json` and the lock. Exit `0` the host is running and healthy, `10` no host is running, `11` running but unhealthy (the snapshot is stale or a section is unavailable or degraded).

**Send a test message to Discord.** `main.py alert test` sends one message to every configured channel and prints what each answered; it writes nothing and takes no lock, so it runs beside the running host. The webhook exists only inside the unit, so run it with the unit's credential:

```bash
sudo systemd-run --wait --pipe --quiet --uid=sew --gid=sew \
  -p LoadCredential=alerting_discord_webhook:/etc/sew/credentials/alerting_discord_webhook \
  -E PYTHONPATH=/opt/sew -E SEW_DATA_ROOT=/var/lib/sew \
  /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py alert test
```

Exit `0` the message was taken (check that it arrived: "sent" means Discord accepted it, not that you read it), `5` no channel is configured or Discord refused the webhook (a 401 or 404: it was deleted; rotate it as in §3), `1` Discord did not answer or asked to wait. The answer names the status, never the URL.

## 6. Day to day

**How the reports look (`BOT-195`, [`PRO-017`](../../Tasks/proposal/PRO-017.md)).** Typed at a terminal, the text reports (`bot list`, `bot show`, `bot order`, `status`, `exchange-status`, ...) print as a table or an aligned block with a bold header, and a state or a profit figure is coloured (`RUNNING` green, `PAUSED` and `RECOVERING` yellow, `HALTED` and `ERROR` red; a loss red, a profit green). The word or the minus sign is always printed too. **Anything that is not a person at a terminal gets exactly the plain text the report always had**: a pipe or a file, the systemd journal, `ssh host command` without a terminal, `NO_COLOR` set to any value, `TERM=dumb`, a terminal too narrow for the table, and a venv where `rich` is not installed. `--json` is never touched. To turn the tables off on a terminal, set `NO_COLOR=1` (`NO_COLOR=1 main.py bot list`). The logs are not coloured: the journal keeps plain text (§10). The server needs `rich`, which `pip install -r requirements-headless.txt -c requirements.lock` installs (a pure-Python wheel, about 2 MB with its two small dependencies); without it the reports are plain.

| Want | Linux | Windows |
| :--- | :--- | :--- |
| Start / stop / restart | `systemctl start\|stop\|restart sew-run` | `nssm start\|stop\|restart sew-run` |
| Run at boot | `systemctl enable sew-run` | set by the install script (`SERVICE_AUTO_START`) |
| Is it alive and what does it hold | `main.py status` (as §5) | the same, from the service account or an Administrator who sets `SEW_DATA_ROOT` |
| What orders does one bot hold (as its file records them, not from the exchange) | `main.py bot order <id> [--json]` (below) | the same |
| Stop, pause, resume, start or edit one bot without stopping the host | `main.py bot stop\|pause\|resume\|start <id>` or `bot edit <id> --set key=value` as the service account (below) | the same, from the service account |
| Follow the log | `journalctl -u sew-run -o cat -f` | `Get-Content C:\ProgramData\sew\service-logs\sew-run.log -Wait` |
| Only problems | `journalctl -u sew-run -o cat \| grep -E ' - (WARNING\|ERROR\|CRITICAL) - '` | `Get-Content C:\ProgramData\sew\service-logs\sew-run.log \| Select-String ' - (WARNING\|ERROR\|CRITICAL) - '` |

**Reading the health line** (full table in [`LOGGING.md`](LOGGING.md) §4): `[health] state=SERVING up=3600s bots=running:3,paused:1,halted:0,recovering:0,error:0,starting:0,stopping:0,awaiting_recovery:0 tick_age_s=2 stream_down_s=5 skew_ms=-120 rss_mb=310`. It is progress, not liveness: alert yourself when the line stops appearing, when `tick_age_s` or `stream_down_s` keep growing, when `halted`, `error` or `recovering` is above zero that you did not expect, when `starting` or `stopping` stays above zero for minutes, or when `skew_ms` approaches 1000. `na` means "not measured yet".

**Judging a 24-hour run clean** (`BUG-209`). In normal mode (no `--dev`, no `--debug`) a clean run has **no** record matching ` - (WARNING|ERROR|CRITICAL) - ` except the one `[alerts]` WARNING at start, and every `[health]` line shows `halted:0,error:0`. Anything else is a finding. What reaches those levels, by tag, is the table in [`LOGGING.md`](LOGGING.md) §6: a bot that lands in HALTED is a WARNING and one that lands in ERROR is an ERROR (`[bot-transition]`, with the reason), an event the lifecycle refuses is a WARNING (`[bot-transition-refused]`), a fill or an order end the stream lost and a reconcile recovered is a WARNING (`[missed-fill]`, `[missed-end]`), a periodic read that fails is one WARNING per streak and one INFO when it recovers (`[refresh-failed]`, `[refresh-recovered]`), a clock above 500 ms from the exchange is a WARNING and at 1000 ms an ERROR (`[clock-skew]`), and a market stream that failed is an ERROR (`[kline-stream]`).

**A process that was killed says nothing in the app's log.** A hard kill or the kernel's OOM killer leaves no line of the app's own, and systemd's lines (`Main process exited`, `Scheduled restart`) do not match the grep above. Besides the grep, check `systemctl show sew-run -p NRestarts` (it should be `0` for a run nobody restarted) and `journalctl -u sew-run | grep -E 'Main process exited|Scheduled restart'`. After a restart the bots that were running come back RECOVERING, one `[recovering]` WARNING each (§11 row 2).

### The orders one bot holds (`bot order`)

`BOT-187`. `main.py bot order <id>` prints, per order, the grid level, side, price, quantity, executed quantity, the level's state as the file records it (`RESTING`, `PARTIAL`, ...) and the client order id: the rows the Bots tab's "orders" table shows. It is **read-only** (like `bot show`: it takes no lock, works beside a running host and on a read-only copy of the data root) and **stored, not live**: it reads the bot's saved run record and asks the exchange nothing, so with no host running, or after a crash, the file can be behind the exchange. The text says so in its first line, and `--json` carries `source: "stored"` and `app_running`. A bot with no run prints `No orders.`; a RUNNING bot whose run record cannot be read prints `Orders unknown` (never `No orders.`); a bot file this build cannot read is named with its path; an unknown id exits `2`. Live open orders need an order session and are a separate, later command.

### The ladder and where the price stands (`bot show`, `bot show --grids`, `bot list`)

`BOT-193`. `main.py bot show <id>` also prints, after the earnings, the rows the Bots tab's Plan panel shows: `Ladder` (the spacing model, the smallest and largest step in per cent, the average profit of one cycle and the fee it is before or after), `Average per cycle (net of fees)` (what a completed cycle booked on average: grid profit over cycles, net of both legs' fees and without Futures funding), `Last price heard` (the last price the bot heard and how long ago), `Lower edge` and `Upper edge` (the range edges, with the distance from that price in per cent), `Stop loss` and `Take profit` (`off`, or the price with its distance) and, on Futures, `Liquidation price`. `bot show <id> --grids` adds one row per grid: the buy and the sell level above it, the step, the net step, the profit of one cycle before and after fees, and what the saved run says that grid is doing (`waiting to buy`, `waiting to sell`, `waiting to buy and sell` where the price stands, `no order`, `not recorded`). `bot list` has a `GRID STEP` column (`1.45% to 1.67%`, top to bottom, or `1.20% each`). An amount that two decimals would round to zero is written `less than 0.01`, never `0.00`. Like `bot order` they are **read-only** and **stored, not live**: they come from the bot's saved file, ask the exchange nothing, take no lock and need no host, and the ladder is built from the bot's **current saved parameters** (a `bot edit` shows at once), so the levels are the parameters' raw levels, within one tick of the resting orders.

Read each figure by its label: the steps and the net step are *designed* (from the parameters), the profit per cycle is an *estimate* (the capital over the `grid_count` levels that hold an order, not a promise: the bot sizes each order by the exchange's lot step and its opening price), and the state of a grid is *recorded* (the saved run). Nothing here says how often the price will cross a level and there is no profit per day. **The account's maker fee rate is recorded in the bot's file when a run starts (`BOT-194`), and with it the net step and the profit per cycle after fees are filled in; the `Ladder` line then says "after the 0.02% maker fee on both legs (rate recorded at run start)", the net columns of `--grids` are headed with the run-start rate and a note under the table names it, and the Bots tab words the same figures "after fees (run-start rate)".** It is the rate of that start, not today's: a fee tier change later leaves it stale until the next start, and a resume keeps it. A bot whose run began before this build recorded none, so it reads "before fees: no maker rate is recorded for this run" and prints `—` in the net columns until it is started again. **The Futures liquidation price is the exchange's report and is not saved, so `Liquidation price` says it is not in the record.** A price the bot has not heard is `no price yet` and its distances are left out, never zero. When the saved run's resting orders are not on the rungs of the current parameters (they were edited after the run began) every grid says `not recorded` and a note says why. `--json` carries all of it under `ladder` (in a `bot list` the summary and the price position, with `rows` empty; exact decimals as text, `null` where unknown; `rows[].state` is the state's name, `position.age_seconds` an integer; `ladder.available` is `false` with a `reason` for a bot whose parameters make no ladder or whose kind has none).

### How much has a bot earned (`bot list`, `bot show`)

`BOT-192`. `main.py bot list` has three columns, `GRID PROFIT`, `CYCLES` and `TOTAL PNL`, and `bot show <id>` four rows in this order, `Grid profit`, `Cycles`, `Total PnL` and `Unrealised`: the figures and the words of the Bots tab, whose table has the same `Grid profit`, `Cycles` and `Total PnL` columns and whose detail panel lists "Profit from completed cycles" first, then the cycles, the total and "of which unrealised". **Grid profit is what the completed buy/sell cycles booked, net of the fees of both legs of each cycle, and excludes a Futures bot's funding.** The total adds what is still held, at the price the bot itself last heard (`Unrealised` shows that part, with the price), and the funding; read the grid profit for "what has the bot earned", the total for "where does the bot stand". Like `bot order` they are **read-only** and **stored, not live**: they come from the bot's saved run record, ask the exchange nothing, take no lock and need no host, so they work beside a running host and on a read-only copy; with no host running they are what the last run saved. A figure the record cannot give is never printed as zero: `—` means the bot has no readable run record (a draft, or a record this build cannot read) or, for `Unrealised`, holds nothing; `no price yet` means the figure waits for a price the bot has not heard (it holds base and has seen no tick); a fee that could not be priced is named after the total. A new run of the same bot (stop, then start) begins a new record, so its grid profit starts again from zero cycles. `--json` carries them under `earnings` (`null` when there is no run record): `grid_profit`, `total_pnl`, `unrealised` and `mark_price` are exact decimals as text and `null` while unknown (`total_pnl`, `unrealised` and `mark_price` wait for a price), `completed_cycles` and `unpriced_fees` are integers.

### Control one bot on the running host (`bot stop`, `bot pause`, `bot resume`, `bot start`, `bot edit`)

`EPIC-038J`, `EPIC-038K` and `EPIC-038L`, decision O4 (the owner chose a local command directory). The host holds the data root's lock, so a second shell cannot change a bot itself; instead it hands the host a **command**, and the host runs the same Stop, Pause, Resume, Start or Save the Bots tab runs.

```bash
M="sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py"
$M bot show 44wa1x                  # what state is it in?
$M bot show 44wa1x --params         # every stored parameter, key and value, sorted by key (reads the file: works beside a running host)
$M bot stop 44wa1x [--confirm-venue spot_mainnet]   # Spot: cancel its orders, keep the coin, STOPPING then STOPPED
$M bot stop 44wa1x --close-position [--confirm-venue futures_mainnet]   # Futures: cancel its orders and close the position at market
$M bot pause 44wa1x                 # place no orders; the resting ones stay
$M bot resume 44wa1x                # a PAUSED or RECOVERING bot; mainnet RECOVERING: add --confirm-venue spot_mainnet
$M bot start 44wa1x [--confirm-venue spot_mainnet]  # a DRAFT or STOPPED bot, once; the other bots are not touched
$M bot edit 44wa1x --set lower=81000 --set upper=90000   # a DRAFT or STOPPED bot's parameters; it lands on DRAFT; places no order
```

- **Who may do it.** Only the account the host runs as (`sew` above). The host makes `state/control/` mode `0700` when `run` starts; each command is a file mode `0600` in it, and the host refuses any file that is not owner-only and the host account's own (on Windows, an ACL of the service account and the administrators). There is no password and no port: the host opens **no listening socket** for this (a test reads the host's sockets). An account that cannot write the directory gets exit `5`; a host that is not a `run` host (the desktop app) has no directory and gets exit `5` too.
- **What you see.** The command waits for the host's answer (`--wait`, 15 s by default) and prints the host's own sentence. Exit `0` the bot accepted it; `2` the bot's own rule refused it (not found, not in a state that allows it, a HALTED bot to resume...) and nothing changed; `5` this account has no control; `10` **no host is running, nothing was written**; `11` a host is running and recorded no answer in time (the command is withdrawn if the host never took it; see the audit). A stop is asynchronous: `0` means STOPPING. Check `bot show` for STOPPED.
- **At most once.** Every command has an id; the host writes `received` to `state/control/audit.jsonl` before it acts and the verdict after (`executed`, `refused`, `failed`, `malformed`, `unauthorised`, `replayed`, `expired`). A file with an id the host has seen is a replay and does nothing, even after a restart. A file older than 5 minutes (or dated more than 1 minute ahead of the host's clock) is `expired`: it does not run late. The audit is append-only, grows by two lines a command and is never rotated; it holds ids, actions and sentences, never a secret.
- **A HALTED bot is not resumed this way.** Its resume proposes a ladder that a person reads and confirms; use `run --resume-halted` (below) or the Bots tab.
- **A Stop opens a closed order session first** (the owner's answer "B", 2026-10-17). An Emergency Stop or a restart closes the venue's order session, and a stop cannot finish without it, so `bot stop` opens it as Start and Resume do. Opening it reconciles every bot on that venue with the exchange, exactly as `run --resume-recovering` does. **After a host restart every bot that was running is RECOVERING, and opening the session returns each of them on that venue to the state it had before the restart: a RUNNING bot trades again, not only the one you stop.** On a mainnet venue the session uses real money, so add `--confirm-venue spot_mainnet`; without it the stop is refused, nothing is opened, and the refusal names the other RECOVERING bots it would return; an already open session, or a testnet, needs no answer. The host's own shutdown stop (`--on-stop stop-bots`) still opens nothing.
- **A Futures bot is stopped only with `--close-position`** (`BUG-224`). A leveraged position is never kept when a bot stops (no stop stands on the exchange for it yet, `EPIC-039H`), so `bot stop` on a Futures bot **without** the flag is refused with exit `2` and changes nothing; the refusal says that stopping closes the position at market and names the flag. With the flag the host runs the Bots tab's "Close the position at market": the bot's orders are cancelled and its position is closed by a reduce-only market order, at the market price, and on `futures_mainnet` that is real money. The flag is the whole consent to the close; `--confirm-venue` is still what opens a closed mainnet order session. On a Spot bot the flag sells the coin the bot holds, as the screen's close does; without it the coin is kept. The host's shutdown stop (`--on-stop stop-bots`) still keeps and so still leaves a Futures bot: it is refused, listed as left, and stopped later with `bot stop <id> --close-position`.
- **Start one bot, with no restart of the host** (`EPIC-038K`). An older host that is sent `start` reads the unknown action as a malformed command and does nothing (exit `1`, audited `malformed`): upgrade the host before using this verb. `bot start <id>` runs the Start the Bots tab and `--start-planned` run, once, and audits it; it starts that bot and no other. Only a DRAFT or STOPPED bot starts. The Start's own checks refuse it in words: **one active bot per symbol** (`ONE_ACTIVE_BOT_PER_SYMBOL`, naming the holder), **at most five active bots per venue** (`VENUE_FULL`), and **a venue that holds a RECOVERING bot starts nothing** (`VENUE_RECOVERING`: starting opens the order session, which would return the waiting bots to trading, so resume or stop them first, §8 "Bots on more than one venue"). A HALTED or AWAITING_RECOVERY bot is refused with exit `2`: its resume proposes a ladder a person reads, so use `run --resume-halted` or the Bots tab. On a mainnet venue the start uses real money: add `--confirm-venue spot_mainnet` (or `futures_mainnet`); without it nothing is opened or started and the refusal names the venue's other RECOVERING bots, because opening the order session reconciles them. A Futures start is the same Start and costs the same request weight (about 300).
- **Edit one bot's parameters, with no restart of the host** (`EPIC-038L`). The case it was built for: `bot start sj9rno` is refused ("The price 81233 is below the range's lower bound 81305. Starting now would buy ... Lower the range to include the price"), and `bot apply` cannot correct it because the running host holds the data root ("Another copy ... read-only"). So: `bot stop <id>` until `bot show` says STOPPED (a DRAFT bot needs no stop), then `bot show <id> --params` to read the current values, `bot edit <id> --set lower=81000`, then `bot start <id>`. The other bots keep trading throughout. `bot edit` is the Save of the Bots tab for one bot: the lifecycle table decides (only **DRAFT and STOPPED**; RUNNING, PAUSED, HALTED, RECOVERING, AWAITING_RECOVERY, STARTING, STOPPING and ERROR are refused in words, exit `2`, nothing changed), and the bot lands on **DRAFT**, so it does nothing until `bot start`. It is an edit and not an order: it needs **no `--confirm-venue`**, even on `spot_mainnet` or `futures_mainnet`, and opens no order session; the real-money question stays at `bot start`, whose guard is untouched.
  - **What you read first.** `bot show <id> --params` prints every parameter the bot stores, one row per key, sorted by key, values exactly as stored (no rounding; `--json` carries them under `parameters`, `--format` works as for every report). It is a plain read of the bot's file, so it works on the read-only copy beside the host with no command file and no host round trip. The keys it lists are the ones `--set` accepts.
  - **What you type.** `--set key=value`, repeated, at most 16, each parameter once. Every parameter is text (a number as written, no quotes needed: `lower=81000`, `spacing=GEOMETRIC`, `stop_loss=percent:5`), exactly as in a plan file; the bot's kind says which keys exist and which values it can read. A Grid's keys are `lower`, `upper`, `grid_count`, `spacing`, `capital_quote`, `stop_loss`, `take_profit` and, on a position venue, `direction` and `leverage` (named together) and `on_range_exit`. A key or a value is 1 to 32, respectively 1 to 64, characters of letters, digits and `_ . : + -` (no spaces or quotes), because the file crosses a trust boundary. The same checks as the Bots tab refuse an **unknown key** or a **value the kind cannot read** (`lower is not a number`, `upper must be above lower`, `grid_count must be at least 1`) in words, exit `2`, **and change nothing**: one bad setting among good ones refuses all of them, and a STOPPED bot stays STOPPED. A set whose values are the bot's own already is refused ("nothing to change"), so a STOPPED bot is not moved to DRAFT for nothing. What needs the exchange (the venue's filters, the account, `on_range_exit=close` on Spot) is still judged by `bot start`.
  - **What you see.** The reply names each change as `key old -> new` (`(unset)` for a parameter the bot did not hold) and says the bot is DRAFT.
  - **Your plan file is not updated, and neither is `state/bot_plan.json`.** `bot apply plan.json` is declarative and the file is yours; the applied record holds a desired state per bot and no parameters, so there is nothing in it to update. **After `bot edit`, change the same value in `plan.json` too: otherwise the next `bot apply` of the old plan sees the bot's parameters differ from the plan, edits them back (an EDIT entry lands the bot on DRAFT again) and the old range returns.** `bot export --bot-id <id> --output new-plan.json` writes the bot as it is now, if you prefer to regenerate the entry.
  - **An older host** reads `edit` as an unknown action and `set` as an unknown key: it audits the command `malformed`, executes nothing and the verb exits `1`; upgrade the host before using it.
  - **It cannot race a start.** The edit runs under the same lock a Start holds while it reads the bots and moves one to STARTING, on the host's command thread like the other verbs: either the Start has moved the bot first (the edit is refused: it is STARTING) or the edit landed first (the Start reads the new parameters). A bot at rest has no worker and so no queue of its own; the write is the one the Bots tab's Save makes.
- **Delete is not a running-host command.** `bot delete` was dropped from `EPIC-038K` by the owner (2026-10-17). A DRAFT or STOPPED bot is still deleted with the host stopped, by `bot apply --prune` (§8); there is no `delete` action word in the command file.
- **To free the symbol for a new run:** `bot stop <id>` until `bot show` says STOPPED, then `bot start <id>` again (after `bot edit <id> --set ...`, the Bots tab, or applying a plan with the host stopped), or stop the host, `bot apply plan.json [--prune]` and start it with `--start-planned` (§8). `bot apply` itself still needs the host stopped.

## 7. What the exit codes mean for you

The full table is [`exit_codes.md`](exit_codes.md). The ones a service meets:

| Code | systemd does | You do |
| :-: | :--- | :--- |
| `0` | nothing (a requested stop, or a second signal) | nothing |
| `1` | restarts after 10 s | read the traceback in the journal; a crash loop is a bug to report with the log **file** |
| `2` | does not restart | a flag in the unit is wrong; `journalctl` names it |
| `3` | does not restart | another copy holds the data root: a second `run`, or the desktop app on the same `SEW_DATA_ROOT`. Stop it |
| `4` | does not restart | a machine check failed: the table in §4 |
| `5` | does not restart | the key: absent, rejected, can withdraw, or `--resume-recovering` / `--resume-halted` without an alert channel; §3 and §4 |
| `6` | restarts after 10 s | the exchange is down or unreachable; it retries until it is back |

After fixing a code `2`–`5` cause, `systemctl reset-failed sew-run && systemctl start sew-run`.

## 8. Upgrade and rollback

The state is the data root's `state/` (the bots' files, the alert outbox, the snapshot). The upgrade **leaves resting orders on the exchange** (the default stop, §0) and nothing watches them while the host is down; do it when that is acceptable. `--on-stop stop-bots` cancels first, but it is a flag of the process being stopped: it only applies if the running host was *started* with it (a drop-in for `ExecStart`).

```bash
# 1. See what is running.
sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew /opt/sew/venv/bin/python \
    /opt/sew/Sagittarius_Elite_Warrior/src/main.py bot list
# 2. Stop, and read that it drained: "DRAINING -> STOPPED" and "workers closed", exit 0.
sudo systemctl stop sew-run
journalctl -u sew-run -o cat -n 40
# 3. Copy the state aside (the way back).
sudo cp -a /var/lib/sew/state "/var/lib/sew/state.before-$(date +%F)"
# 4. Upgrade the code and its dependencies.
sudo git -C /opt/sew/Sagittarius_Elite_Warrior fetch --tags
REF='<the release tag or commit>'   # edit this line first
sudo git -C /opt/sew/Sagittarius_Elite_Warrior checkout "$REF"
sudo /opt/sew/venv/bin/pip install -r /opt/sew/Sagittarius_Elite_Warrior/requirements-headless.txt \
    -c /opt/sew/Sagittarius_Elite_Warrior/requirements.lock
sudo /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/scripts/engine_pin.py install
sudo /opt/sew/venv/bin/python -m compileall -q /opt/sew/Sagittarius_Elite_Warrior   # the sew user cannot write bytecode (§2)
# 5. Regenerate the unit if the release changed it, then:
sudo cp /opt/sew/Sagittarius_Elite_Warrior/deploy/linux/sew-run.service /etc/systemd/system/ && sudo systemctl daemon-reload
# 6. Pre-flight (testnet: §4; mainnet: the start does it), start, look.
sudo systemctl start sew-run
sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew /opt/sew/venv/bin/python \
    /opt/sew/Sagittarius_Elite_Warrior/src/main.py status
```

Read the `[preflight]` lines after the start. **`bot-files-readable` WARN** means a bot file was written by a newer build than this one and its bot is not loaded; `status` and `bot list` list that file with its path and reason (`unknown schema_version 2`). The file is never rewritten. Every bot a restart found RUNNING or PAUSED is now RECOVERING and **stays so until a person resumes it**; one WARNING per bot names it (§0).

**Rollback**: stop, `git checkout` the previous release, reinstall its dependencies (step 4), and put the state back from step 3 **if the newer build has written bot files** (an older build refuses a newer file and leaves it; restoring the copy returns the bots as they were). Start and check as above.

### Which halts a bot recovers from by itself (`bot show`)

`bot show <bot_id>` prints the bot's effective recovery table, one `Recovery` row per halt reason: how long the cause must stay clear before an attempt, how many of the bot's attempts are used inside that rule's window, how long a wait may last before you are told, and which layer decided it. A Futures bot prints `no automatic recovery (futures layer)`. `--json` carries the same rows under `recovery`, and `reason_detail` carries the words the bot wrote beside its reason (where "the automatic recoveries are used up; resume by hand" is said). `bot list` and `status` carry `recovery: null`.

### Plan files and version control (`bot export`, `bot apply`, `run --start-planned`)

A plan is a JSON file (`sew.bot-plan/1`) that names each bot by name and venue and holds **no key, secret or account identifier**, so it is safe to keep in version control and to review as a diff. It is how a server's bots are defined without the desktop app. The desktop app's Bots → Export plan… writes the same file (same query, same never-overwrite writer), so a bot designed there reaches the server with `scp`; it defaults to *All stopped* when a mainnet bot is in scope, so a copied plan starts nothing under `--start-planned` until you change `desired_state` on purpose. The procedure, each step run as in §5 (`M` is the `sudo -u sew env ... main.py` prefix there):

```bash
M="sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py"
$M bot export --all --output /var/lib/sew/plan.json   # once; read-only; never overwrites a file
# edit plan.json (or keep it in git and copy it over), then:
$M bot apply /var/lib/sew/plan.json --dry-run         # prints what would change; changes nothing; works beside a running host
sudo systemctl stop sew-run
$M bot apply /var/lib/sew/plan.json [--prune]         # creates and edits bots (with --prune deletes the ones the plan omits, if at rest); starts and stops nothing
sudo systemctl start sew-run
```

- `bot apply` changes bots, so it needs the data root's lock: with the host running it exits `3` and changes nothing (`bot stop`, `bot pause`, `bot resume`, `bot start` and `bot edit` are the commands that reach a running host, §6; `bot apply --prune` deletes only with the host stopped). A real apply is a **writable boot**, so the restart rule runs first, as at any start: a bot saved as RUNNING or PAUSED becomes RECOVERING in its file (the same state the next `run` would have made it). `--dry-run` boots read-only and changes nothing, which is why it is safe beside a running host. A second apply of the same plan changes nothing. An entry that would edit a bot in a state the lifecycle forbids (it must be stopped first) is reported, not applied, and the command exits `2`; the other entries are applied.
- **A `bot edit` on the running host is not in your plan file.** It changes one stopped bot's parameters while the host runs (§6) and leaves `plan.json` and `state/bot_plan.json` as they were; the next `bot apply` of the old plan edits the bot back to the plan's values. After a `bot edit`, change the same value in `plan.json`.
- `apply` records what the plan wants in **`state/bot_plan.json`** (beside the bots' files, keyed by bot id). **Only that applied record is what the host reads**, never the file you edit, so an edit counts once it has been applied.
- **`run --start-planned`** starts the bots the applied plan says are running and that are at rest. It is not in the unit by default. With no applied plan, or a record that cannot be read, it exits **`5`** before anything boots, which the unit does not restart; so add it to the unit only after a plan has been applied. To add it, use a drop-in (`sudo systemctl edit sew-run`): write `[Service]`, an empty `ExecStart=`, then `ExecStart=` followed by the unit's own line with ` --start-planned` appended.

  `systemctl edit` opens an editor. Its `--stdin` option needs systemd 256 or newer, and Ubuntu 24.04 ships 255, where it answers `unrecognized option '--stdin'`. To do it without an editor, write the drop-in file yourself:

  ```bash
  sudo mkdir -p /etc/systemd/system/sew-run.service.d
  sudo tee /etc/systemd/system/sew-run.service.d/override.conf > /dev/null <<'EOF'
  [Service]
  ExecStart=
  ExecStart=/opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py run --stop-timeout 25 --health-interval 60 --on-stop leave-orders --host-signal sdnotify --start-planned
  EOF
  sudo systemctl daemon-reload
  sudo systemctl reset-failed sew-run
  sudo systemctl restart sew-run
  systemctl cat sew-run | grep -E "LoadCredential|ExecStart"   # the drop-in's lines come last and win
  ```

  On a testnet-only server without the four credential files (§3), add the line `LoadCredential=` under `[Service]` in the same file.
- A bot on a **mainnet** venue is started only with `--confirm-venue <venue>` in the same line; without it the host exits `2` and starts nothing. One `--confirm-venue` names one venue.
- **`--resume-halted`** (`EPIC-042E`) is a person's Resume and Confirm answered in advance, for every bot that is `HALTED` or `AWAITING_RECOVERY` (no other state): the exchange is read, the order session is opened and the ladder the bot proposes is laid, with the price re-read and its tolerance applied. Read the `[resume-halted]` lines after the start: one INFO per bot resumed, one WARNING per bot that stays as it was, with the reason in the words the Resume gave (a session that would not open, a readiness check, a missing `--confirm-venue`). With both flags the halted bots are resumed first, so only a halt that existed before this start is re-planned, never one the recovering reconcile makes in the same start. Unlike `--resume-recovering`, a mainnet bot whose venue was not typed is **skipped and named**, not a reason to refuse the run. The host refuses (exit `5`) without an alert channel or `--i-accept-silent-failures`, as `--resume-recovering` does. The owner does not read the proposal on a headless host; use the flag for a halt you have judged transient (a bot halted for `price_feed_stale` whose bot-halt alert you read), and keep the Bots tab for any other.

### Bots on more than one venue, and several on one (`EPIC-029J1a`, `EPIC-029J1b`)

Bots run together on different venues (Spot or Futures, mainnet or testnet), and on one venue they run together on **different symbols**, up to **5 active bots per venue** (`MAX_ACTIVE_BOTS_PER_VENUE`, the owner's choice of 2026-10-17; a venue is Spot or Futures, mainnet or testnet, so one mainnet account may run five Spot and five Futures bots). Start, the plan's `--start-planned` and the Bots screen ask the same question, so what the screen lists is what the host is told.

- **`--start-planned`**: planned bots on different symbols of one venue all start, up to the venue's five; planned bots on a testnet and on a confirmed mainnet venue both start. Of two planned bots on the **same symbol** of a venue the lowest bot id starts (the run goes in bot-id order) and the other logs `[start-planned] bot <id> was not started: ONE_ACTIVE_BOT_PER_SYMBOL (A bot on <venue> is still active on <symbol> (<id>); ...)`; a sixth bot of a venue logs `VENUE_FULL`. Each stays at rest. **Mind the start weight:** a Futures Start costs about 300 request weight, so a plan of five bots on one Futures venue spends about 1,500 of the minute's 2,400 in its first minute, and the gate (70 %, 1,680) closes before a sixth; a start the closed gate refuses reads `Not connected: exchange asked for a pause` and succeeds on a later run. Idle, each Futures bot costs about 175 weight a minute.
- **A restart with bots waiting to recover blocks new starts on their venue.** `--start-planned` after a restart logs `[start-planned] bot <id> was not started: VENUE_RECOVERING (...)` for every planned bot of a venue that has a `RECOVERING` bot: starting one would open the order session, and the session's opening reconciles (resumes) the bots waiting for it. Run `--resume-recovering` first (or stop those bots), then start the rest. `--resume-halted` and a stop through the command directory also open the session and therefore reconcile `RECOVERING` bots of that venue; that is `BOT-183`, so resume the recovering bots deliberately before using either on a venue that has some. A `bot start` on the running host is refused for the same reason (`VENUE_RECOVERING`), and on a mainnet venue its refusal for a missing `--confirm-venue` names those bots.
- **`--confirm-venue` names one venue per run.** Real-money bots on **two mainnet venues** cannot all be started or resumed by one run: `--start-planned` and `--resume-recovering` judge every wanted real-money bot before anything boots and exit `2` while any is on an unconfirmed venue, naming `--confirm-venue <first venue>` and "one mainnet venue per run". `--resume-halted` skips and names the unconfirmed venue's bots instead (WARNING per bot) and resumes the confirmed venue's. To bring both venues' bots back, keep the other venue's bots out of the run (stopped, or not in the plan) or start them from the Bots tab of the desktop app on the same data root. The owner decided (2026-10-17) to keep one venue per run for now; confirming several is a separate, later task.
- **Emergency Stop and a rate limit act on one venue.** An Emergency Stop halts **every** bot of the venue it was given and none on the other. A rate limit (or the used weight reaching 70 % of the minute's) closes **that venue's** requests, for every caller, until the exchange's pause or the minute ends. Each bot that then needs an order halts `RATE_LIMITED` and resumes by itself at the pause's end (all of them at the same instant); a bot that only reads says so in the log and keeps its ladder; the other venue is unaffected. The venue's orders are also paced together (one 250 ms pacer per venue), so a ladder of 20 orders takes about 5 s and a neighbour's orders queue behind it. Only orders that build a ladder or open a position wait in that queue; a protective stop, a reduce-only close and a Spot exit never do.
- **A refused bot file counts as active on every venue** (its venue is unknown): `status` and `bot list` name it, and no Start passes until it is dealt with.

## 9. Install on Windows (NSSM)

*Not run on a Windows machine by its author; §11 is how it is proven.* Decision O5: NSSM is documented as an external tool, Task Scheduler as the stated fallback; neither is a dependency of the app.

1. Python 3.12+, `git`, then the same three steps as §2 with Windows paths: clone to `C:\sew\Sagittarius_Elite_Warrior` (the directory name is required), `python -m venv C:\sew\venv`, `C:\sew\venv\Scripts\pip install -r requirements-headless.txt -c requirements.lock`, then `scripts\engine_pin.py install`.
2. Download NSSM from <https://nssm.cc> to a folder you control (for example `C:\tools\nssm.exe`). Check the download against the publisher's page; the install runs it as an Administrator.
3. From an elevated PowerShell:

```powershell
.\deploy\windows\nssm-install.ps1 -Nssm C:\tools\nssm.exe -Python C:\sew\venv\Scripts\python.exe `
    -Checkout C:\sew\Sagittarius_Elite_Warrior -DataRoot C:\ProgramData\sew
```

The script ([`deploy/windows/nssm-install.ps1`](../../deploy/windows/nssm-install.ps1), generated by the same `render_service_files.py`) is idempotent: every setting is a `nssm set`, so running it again changes nothing. It sets:

- `AppExit Default Restart` and `AppExit 0|2|3|4|5 Exit`: NSSM restarts on every status unless told otherwise, so it ends the service on a clean exit `0` (as the unit's `Restart=on-failure` does) and on the unit's `RestartPreventExitStatus` codes, with `AppRestartDelay 10000`.
- **`AppStopMethodConsole 62000`**: NSSM stops a console program by sending **Ctrl-C first**, which the host handles as `SIGINT` (a drain, then exit 0), and waits this long before it tries `WM_CLOSE` and then `TerminateProcess`. NSSM's default wait is 1500 ms, far below the host's 57 s worst case, which would kill a drain in progress. The figure is the unit's `TimeoutStopSec` in milliseconds.
- `AppStdout`/`AppStderr` to `service-logs\sew-run.log` with `AppRotateFiles 1`, `AppRotateOnline 1`, `AppRotateBytes 10485760`: the log is rotated by the wrapper; the app sets no `log.file`.
- `AppEnvironmentExtra` with `PYTHONPATH` and `SEW_DATA_ROOT`; the service account `NT SERVICE\sew-run` (a virtual account, no password), granted modify on the data root and nothing else.

**Keys on Windows.** There is no `LoadCredential`. For a **mainnet** venue use the permission-checked file store (decision O3's fallback): a directory outside the checkout whose ACL grants only the service account, SYSTEM and Administrators, named by `SEW_SECRET_FILES_DIR`, one file per secret (`futures_mainnet_api_key`, `futures_mainnet_api_secret`, and the spot pair). The store refuses a file anyone else can reach and prints the `icacls` command that fixes it. Whether the Windows Credential Manager works for a service account is **unanswered** (`EPIC-038E`); do not rely on it.

```powershell
$dir = 'C:\ProgramData\sew\secrets'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
icacls $dir /inheritance:r /grant 'NT SERVICE\sew-run:(OI)(CI)R' 'SYSTEM:(OI)(CI)F' 'Administrators:(OI)(CI)F'
$secret = Read-Host -AsSecureString 'futures mainnet key'
$plain = [System.Net.NetworkCredential]::new('', $secret).Password
[System.IO.File]::WriteAllText("$dir\futures_mainnet_api_key", $plain, [System.Text.UTF8Encoding]::new($false))
```

Then install (or re-run the install script) with `-SecretFilesDir C:\ProgramData\sew\secrets`, which sets `SEW_SECRET_FILES_DIR` for the service.

A **testnet** key goes in the service's environment: `nssm set sew-run AppEnvironmentExtra "+BINANCE_FUTURES_TESTNET_API_KEY=<key>"` (the `+` appends). NSSM keeps that in the registry, readable by Administrators: acceptable for a testnet key, not for a mainnet one. **Running the install script again replaces the whole environment list**, so append the testnet variables again afterwards.

**Reboot.** Windows gives a service a limited time to stop at shutdown (`WaitToKillServiceTimeout`, 5 s by default for the system), shorter than a drain. A host that was killed at a reboot has not written `STOPPED`; the next start reads each bot as RECOVERING, as after a crash. The checklist records what a reboot does on your server.

**Task Scheduler (the fallback).** Use it only if NSSM is unacceptable. Per the research this decision rests on (R10, not run here): its restart settings are coarse (a fixed count and interval, no way to say which exit codes not to restart on, so a configuration fault would loop), and it has no setting that sends Ctrl-C first, so a stop ends the process outright and no drain runs. It can start a task at boot with highest privileges and "run whether the user is logged on or not"; everything else in §6–§8 is the same.

## 10. Logs

The host writes to standard output only. systemd's journal captures and bounds it (`SystemMaxUse=` in `journald.conf`, `journalctl --vacuum-time=14d`); NSSM rotates what it captures. If you set `log.file` anyway it grows without bound until the Engine gains rotation (decision O7); [`LOGGING.md`](LOGGING.md) §2 has the `logrotate` stanza and says why `copytruncate` is required. Do not restate it here.

**Commands that only read, and short-lived commands that write, keep their log off the console** (`BOT-185`, `BOT-186`). `status`, `bot list`, `bot show`, `plan`, `alert test`, `preflight`, `exchange-status` and the other commands that open a read-only copy, and the short-lived writer `bot apply`, print their result and nothing else (the `bot apply` table and any `--confirm-venue` refusal are still on the console): the 60-odd INFO lines of the boot go to `<data root>/logs/cli-<UTC timestamp>-<pid>.log`, one file per command run (`/var/lib/sew/logs/` on Linux, `C:\ProgramData\sew\logs\` on Windows), the newest 40 kept, each capped at 512 KiB (20 MiB at most). A WARNING or ERROR still appears on the console, on stderr, so a failed command is never silent, and a `--json` document on stdout is untouched. To read the log of the run you just made, `ls -t <data root>/logs/cli-*.log | head -1`; for the whole picture add `--verbose`, which puts every record on the console as it was before (`main.py bot list --verbose`, anywhere on the line). `run`, `sync`, `stream` and `trade-once` are not affected: a `keeps_console_log` command's log stays on standard output, which the supervisor above rotates (or is its progress). The design and its trade-offs: [`LOGGING.md`](LOGGING.md) §1b.

## 11. The checklist the owner signs

Testnet only. Two machines: a fresh Linux VPS and a fresh Windows server. **Not run yet**; each row is filled in with the date, the result and the log line that proves it, and signed.

| # | Do | Pass when | Linux | Windows |
| :-: | :--- | :--- | :-: | :-: |
| 1 | Install per §2 / §9, provision the testnet keys, start | `status` exits 0; the journal shows `BOOTING -> SERVING` and a `[health]` line | ☐ | ☐ |
| 2 | `kill -9` the process (Windows: end the task in Task Manager) | the service restarts within ~15 s; bots that were running are RECOVERING and named in a WARNING each; `[health]` lines resume; the alert for the crash is the one `EPIC-036` defines (until it merges, none) | ☐ | ☐ |
| 3 | Reboot the machine | the service is running again without a login; record whether `STOPPED` was written | ☐ | ☐ |
| 4 | `systemctl stop` / `nssm stop` while a bot is RUNNING | the log shows `DRAINING -> STOPPED` and `workers closed`; the stop took less than `TimeoutStopSec`; exit 0; orders are still on the testnet exchange | ☐ | ☐ |
| 5 | While the service runs, start a second service on the same data root (Linux: a copy of the unit named `sew-run2`; Windows: a second NSSM service) | the second exits `3` and its supervisor does **not** restart it (`systemctl status` shows `failed`, one start only; NSSM shows it stopped); the first is unaffected; remove the second | ☐ | ☐ |
| 6 | Set the clock 2 s ahead, start | the pre-flight fails `clock-skew` (exit 4) and the unit is not restarted; fix the clock and `reset-failed` | ☐ | ☐ |
| 7 | Fill the data volume below 100 MiB (a throwaway file) and start | `disk-space` is reported FAIL with its remedy (exit 4); remove the file | ☐ | ☐ |
| 8 | Remove the testnet key and start | exit 5 (`credentials-present`), not restarted | ☐ | ☐ |
| 9 | Put a bot file with `"schema_version": 99` in `state/bots/` and start | the `bot-files-readable` WARN names it; `bot list` lists it; the file is byte-for-byte unchanged | ☐ | ☐ |
| 10 | Upgrade per §8 to the next commit and back (rollback) | the bots return as RECOVERING; the state copy restores them | ☐ | ☐ |
| 11 | Set `log.file` to `/var/log/sew/sew.log` (Linux), install the `logrotate` stanza of [`LOGGING.md`](LOGGING.md) §2, run `logrotate -f` | the file rotates, the app keeps writing to it, nothing is lost beyond the documented `copytruncate` window; then remove `log.file` | ☐ | n/a |
| 12 | Stop the host on purpose and wait the heartbeat interval | the dead man's switch tells you. **Needs `EPIC-036E`; leave unchecked until it merges.** | ☐ | ☐ |

Signed: ____________________ date: ____________ machine: ____________________

## 12. What is proven mechanically, and what is not

Guards in the test suite (`tests/unit/scripts/test_service_files.py`, `test_nssm_install_script.py`, `test_headless_runbook.py`, `test_runbook_shell_snippets.py`): the unit and the NSSM script equal their generator; `RestartPreventExitStatus` equals the exit-code table's non-restarting codes; `TimeoutStopSec` and `AppStopMethodConsole` exceed `--stop-timeout` + the host's grace and snapshot constants; the unit's arguments are accepted by the real command-line parser; no `log.file`, `--dev` or `--debug`; the credential names are the ones the store reads; the hardening leaves the data root and the notify socket open; `systemd-analyze verify` accepts the unit; the NSSM script parses as PowerShell and, run against a stand-in `nssm`, issues the settings above and installs nothing the second time; this runbook names those figures and every pre-flight check; every bash block in it parses and the key-provisioning step is run for real with a placeholder value. On the CI runner a missing `pwsh`, `systemd-analyze` or `bash` fails these tests rather than skipping them.

**Not proven**: `alert test` through `systemd-run` and a message reaching a real Discord channel (the owner's run, recorded in `EPIC-036G`), the unit under a running systemd (no systemd was PID 1 where it was written), the NSSM script on Windows, the reboot and `kill -9` rows above, and the Windows Credential Manager. The checklist is how they get proven.

## 13. Containers

`--host-signal sdnotify` does not work inside Docker unless the host's notify socket is mounted into the container, and systemd credentials do not exist there. A Dockerfile is out of scope for this epic; if you run the app in a container, run `main.py run` without `--host-signal`, supply keys through the container runtime's secrets as environment variables, and let the container runtime restart it with the same policy: do not restart on exit codes `2`–`5`.
